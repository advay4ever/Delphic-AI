"""
Cross-platform local launcher for Delphic AI.

Run this with Python 3.10+ on macOS or Windows:

    python run_app.py
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS_FILE = ROOT / "requirements.txt"
REQUIREMENTS_STAMP = VENV_DIR / ".requirements.sha256"
ENV_EXAMPLE_FILE = ROOT / ".env.example"
DEFAULT_PORT = "5001"
APP_NAME = "Delphic AI"
STARTUP_TIMEOUT_SECONDS = 60
PROVIDER_KEY_NAMES = (
    "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY",
    "MISTRAL_API_KEY", "TOGETHER_API_KEY", "OPENROUTER_API_KEY", "XAI_API_KEY",
    "DEEPSEEK_API_KEY",
)
ENVIRONMENT_RECOVERY = (
    "Stop Delphic AI. Inside the extracted download, rename only .venv to "
    ".venv-backup, then open the launcher again. Do not delete the separate "
    "Delphic AI data folder or saved chats."
)


class LauncherError(Exception):
    """An actionable local setup error, without credentials or a traceback."""


def protect_private_file(path: Path) -> None:
    """Restrict local secrets to the current account on Unix-like systems."""
    if os.name == "nt" or not path.exists():
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass


def protect_private_directory(path: Path) -> None:
    """Restrict a local data directory to the current account on Unix."""
    if os.name == "nt" or not path.exists():
        return
    try:
        path.chmod(0o700)
    except OSError:
        pass


def user_data_dir() -> Path:
    configured_dir = os.getenv("DELPHIC_DATA_DIR")
    if configured_dir:
        return Path(configured_dir).expanduser()
    if os.name == "nt":
        base_dir = os.getenv("APPDATA") or str(Path.home())
        return Path(base_dir) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".local" / "share" / "delphic-ai"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_supported_python() -> None:
    if sys.version_info < (3, 10):
        version = ".".join(str(part) for part in sys.version_info[:3])
        raise SystemExit(
            f"Delphic AI needs Python 3.10 or newer. This Python is {version}."
        )


def ensure_virtual_environment() -> Path:
    python_path = venv_python()
    if VENV_DIR.is_symlink() or (VENV_DIR.exists() and not VENV_DIR.is_dir()):
        raise LauncherError(f".venv is not a normal local folder. {ENVIRONMENT_RECOVERY}")
    if not VENV_DIR.exists():
        print("Creating local Python environment in .venv...")
        venv.create(VENV_DIR, with_pip=True)
    try:
        probe = subprocess.run(
            [str(python_path), "-I", "-c", (
                "import json, sys, pip; "
                "print(json.dumps({'prefix': sys.prefix, 'base': sys.base_prefix, "
                "'version': list(sys.version_info[:2])}))"
            )],
            cwd=ROOT, capture_output=True, text=True, timeout=15, check=True,
        )
        info = json.loads(probe.stdout)
        if (Path(info["prefix"]).resolve() != VENV_DIR.resolve()
                or info["prefix"] == info["base"]
                or tuple(info["version"]) < (3, 10)):
            raise ValueError("Not a supported local virtual environment")
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        raise LauncherError(f"The local Python environment is incomplete or broken. {ENVIRONMENT_RECOVERY}") from None
    return python_path


def dependencies_healthy(python_path: Path) -> bool:
    # Parse markers/pins with the requirement parser already shipped with pip.
    check_installed = """
import importlib.metadata
from pathlib import Path
import sys
from pip._vendor.packaging.requirements import Requirement
for line in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    if not line.strip() or line.lstrip().startswith('#'):
        continue
    requirement = Requirement(line)
    if requirement.marker is None or requirement.marker.evaluate():
        installed = importlib.metadata.version(requirement.name)
        if not requirement.specifier.contains(installed, prereleases=True):
            raise SystemExit(1)
import flask, openai, httpx, dotenv, sympy, PIL, pypdf, docx
"""
    try:
        for arguments in (
            ["-I", "-c", check_installed, str(REQUIREMENTS_FILE)],
            ["-I", "-m", "pip", "check", "--disable-pip-version-check"],
        ):
            result = subprocess.run(
                [str(python_path), *arguments], cwd=ROOT, capture_output=True,
                timeout=30, check=False,
            )
            if result.returncode:
                return False
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def install_dependencies(python_path: Path) -> None:
    if not REQUIREMENTS_FILE.exists():
        raise SystemExit("requirements.txt was not found.")

    current_hash = sha256(REQUIREMENTS_FILE)
    previous_hash = REQUIREMENTS_STAMP.read_text(encoding="ascii").strip() if REQUIREMENTS_STAMP.exists() else ""
    healthy = dependencies_healthy(python_path) if current_hash == previous_hash else False
    if healthy:
        return

    print("Installing or repairing Python dependencies...")
    REQUIREMENTS_STAMP.unlink(missing_ok=True)
    command = [str(python_path), "-m", "pip", "install", "--disable-pip-version-check"]
    if current_hash == previous_hash:
        command.append("--force-reinstall")
    run([*command, "-r", str(REQUIREMENTS_FILE)])
    if not dependencies_healthy(python_path):
        raise LauncherError(f"The installed libraries did not pass their checks. {ENVIRONMENT_RECOVERY}")
    REQUIREMENTS_STAMP.write_text(current_hash + "\n", encoding="ascii")


def ensure_env_file(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    protect_private_directory(data_dir)
    env_file = data_dir / ".env"

    if env_file.exists():
        protect_private_file(env_file)
        return env_file

    legacy_env_file = ROOT / ".env"
    if legacy_env_file.exists() and legacy_env_file != env_file:
        shutil.copyfile(legacy_env_file, env_file)
        protect_private_file(env_file)
        print(f"Copied existing settings to {data_dir}")
        return env_file

    if not ENV_EXAMPLE_FILE.exists():
        raise SystemExit(".env.example was not found.")

    env_text = ENV_EXAMPLE_FILE.read_text(encoding="utf-8")
    env_text = env_text.replace(
        "FLASK_SECRET_KEY=change-me-in-development",
        f"FLASK_SECRET_KEY={secrets.token_urlsafe(32)}",
    )
    env_file.write_text(env_text, encoding="utf-8")
    protect_private_file(env_file)
    print(f"Created private settings in {data_dir}")
    return env_file


def read_env_value(name: str, env_file: Path) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        if key.strip() == name:
            return value.strip().strip('"').strip("'")
    return ""


def looks_like_real_api_key(api_key: str) -> bool:
    placeholders = {
        "your-groq-api-key-here",
        "your-openai-api-key-here",
        "your-anthropic-api-key-here",
        "your-google-api-key-here",
        "your-mistral-api-key-here",
        "your-together-api-key-here",
        "your-xai-api-key-here",
        "your-deepseek-api-key-here",
        "your-real-key-here",
        "gsk-your-key-here",
    }
    clean_key = api_key.strip()
    return len(clean_key) >= 12 and clean_key not in placeholders and not clean_key.startswith("your-")


def warn_if_api_key_missing(env_file: Path) -> None:
    keys = [os.getenv(name, read_env_value(name, env_file)) for name in PROVIDER_KEY_NAMES]
    if not any(looks_like_real_api_key(key) for key in keys):
        print()
        print("When the browser opens, choose an AI provider and paste your API key.")
        print()


def app_is_ready(port: int, token: str) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", "/_launcher/ready", headers={"X-Delphic-Launcher": token})
        response = connection.getresponse()
        return response.status == 204 and response.getheader("X-Delphic-Launcher") == token
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except ProcessLookupError:
        process.wait()


def start_app(python_path: Path, data_dir: Path, env_file: Path) -> int:
    try:
        port = int(os.getenv("PORT", DEFAULT_PORT))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise LauncherError("PORT must be a whole number from 1 to 65535.") from None
    url = f"http://127.0.0.1:{port}"
    token = secrets.token_urlsafe(32)
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["FLASK_DEBUG"] = "false"
    env["DELPHIC_STARTUP_TOKEN"] = token
    env.setdefault("DELPHIC_TRUSTED_HOSTS", "127.0.0.1,localhost")
    env.setdefault("DELPHIC_DATA_DIR", str(data_dir))
    env.setdefault("DELPHIC_ENV_FILE", str(env_file))
    env.setdefault("PYTHONUNBUFFERED", "1")

    print(f"Waiting for Delphic AI to start at {url}...")
    print(f"Settings and chat history are stored in: {data_dir}")
    process = subprocess.Popen([str(python_path), "app.py"], cwd=ROOT, env=env)

    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
        while True:
            if process.poll() is not None:
                raise LauncherError(
                    "Delphic AI stopped before it was ready. Read the startup error above. "
                    "If the port is busy, close another copy or the program using that port."
                )
            if app_is_ready(port, token) and process.poll() is None:
                break
            if time.monotonic() >= deadline:
                raise LauncherError("Delphic AI did not become ready in time. The local server was stopped; try again.")
            time.sleep(0.25)
        print(f"Delphic AI is ready: {url}")
        should_open_browser = os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false"
        if should_open_browser:
            try:
                browser_opened = webbrowser.open(url)
            except (OSError, webbrowser.Error):
                browser_opened = False
            if not browser_opened:
                print(f"Open this address in your browser: {url}")
        return process.wait()
    except KeyboardInterrupt:
        print("\nStopping Delphic AI...")
        return 0
    finally:
        stop_process(process)


def main() -> int:
    ensure_supported_python()
    try:
        if not (ROOT / "app.py").is_file() or not REQUIREMENTS_FILE.is_file():
            raise LauncherError("Extract the entire ZIP into a writable folder before starting the launcher.")
        data_dir = user_data_dir()
        python_path = ensure_virtual_environment()
        install_dependencies(python_path)
        env_file = ensure_env_file(data_dir)
        warn_if_api_key_missing(env_file)
        return start_app(python_path, data_dir, env_file)
    except subprocess.CalledProcessError:
        print()
        print("Delphic AI could not install its Python packages.")
        print("Check your internet connection, then open the launcher again.")
        return 1
    except LauncherError as error:
        print(f"\n{error}")
        return 1
    except (OSError, UnicodeError):
        print("\nDelphic AI could not read or write its setup files or start Python.")
        print("Extract the entire ZIP into a writable folder and check disk space and file permissions.")
        print("If .venv is incomplete, " + ENVIRONMENT_RECOVERY)
        return 1
    except KeyboardInterrupt:
        print("\nSetup cancelled. Open the launcher to try again.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
