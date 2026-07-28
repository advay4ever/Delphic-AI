"""
Cross-platform local launcher for Delphic AI.

Run this with Python 3.10+ on macOS or Windows:

    python run_app.py
"""

from __future__ import annotations

import hashlib
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
    if not python_path.exists():
        print("Creating local Python environment in .venv...")
        venv.create(VENV_DIR, with_pip=True)
    return python_path


def install_dependencies(python_path: Path) -> None:
    if not REQUIREMENTS_FILE.exists():
        raise SystemExit("requirements.txt was not found.")

    current_hash = sha256(REQUIREMENTS_FILE)
    previous_hash = REQUIREMENTS_STAMP.read_text().strip() if REQUIREMENTS_STAMP.exists() else ""
    if current_hash == previous_hash:
        return

    print("Installing Python dependencies...")
    run([str(python_path), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])
    REQUIREMENTS_STAMP.write_text(current_hash + "\n")


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

    env_text = ENV_EXAMPLE_FILE.read_text()
    env_text = env_text.replace(
        "FLASK_SECRET_KEY=change-me-in-development",
        f"FLASK_SECRET_KEY={secrets.token_urlsafe(32)}",
    )
    env_file.write_text(env_text)
    protect_private_file(env_file)
    print(f"Created private settings in {data_dir}")
    return env_file


def read_env_value(name: str, env_file: Path) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text().splitlines():
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
    groq_key = read_env_value("GROQ_API_KEY", env_file)
    openai_key = read_env_value("OPENAI_API_KEY", env_file)
    other_keys = [
        read_env_value("ANTHROPIC_API_KEY", env_file),
        read_env_value("GOOGLE_API_KEY", env_file),
        read_env_value("MISTRAL_API_KEY", env_file),
        read_env_value("TOGETHER_API_KEY", env_file),
        read_env_value("XAI_API_KEY", env_file),
        read_env_value("DEEPSEEK_API_KEY", env_file),
    ]
    if not any(looks_like_real_api_key(key) for key in [groq_key, openai_key, *other_keys]):
        print()
        print("When the browser opens, choose an AI provider and paste your API key.")
        print()


def start_app(python_path: Path, data_dir: Path, env_file: Path) -> int:
    port = os.getenv("PORT", DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.setdefault("PORT", port)
    env.setdefault("FLASK_DEBUG", "false")
    env.setdefault("DELPHIC_TRUSTED_HOSTS", "127.0.0.1,localhost")
    env.setdefault("DELPHIC_DATA_DIR", str(data_dir))
    env.setdefault("DELPHIC_ENV_FILE", str(env_file))
    env.setdefault("PYTHONUNBUFFERED", "1")

    print(f"Starting Delphic AI at {url}")
    print(f"Settings and chat history are stored in: {data_dir}")
    process = subprocess.Popen([str(python_path), "app.py"], cwd=ROOT, env=env)

    try:
        time.sleep(1.5)
        if process.poll() is not None:
            return process.returncode
        should_open_browser = os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false"
        if should_open_browser and not webbrowser.open(url):
            print(f"Open this address in your browser: {url}")
        return process.wait()
    except KeyboardInterrupt:
        print("\nStopping Delphic AI...")
        process.terminate()
        try:
            return process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait()


def main() -> int:
    ensure_supported_python()
    data_dir = user_data_dir()
    python_path = ensure_virtual_environment()
    try:
        install_dependencies(python_path)
    except subprocess.CalledProcessError:
        print()
        print("Delphic AI could not install its Python packages.")
        print("Check your internet connection, then open the launcher again.")
        return 1
    env_file = ensure_env_file(data_dir)
    warn_if_api_key_missing(env_file)
    return start_app(python_path, data_dir, env_file)


if __name__ == "__main__":
    raise SystemExit(main())
