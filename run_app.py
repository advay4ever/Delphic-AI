"""
Cross-platform local launcher for Delphic AI.

Run this with Python 3.10+ on macOS or Windows:

    python run_app.py
"""

from __future__ import annotations

import hashlib
import os
import secrets
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
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE_FILE = ROOT / ".env.example"
DEFAULT_PORT = "5001"


def protect_private_file(path: Path) -> None:
    """Restrict local secrets to the current account on Unix-like systems."""
    if os.name == "nt" or not path.exists():
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass


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


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        protect_private_file(ENV_FILE)
        return
    if not ENV_EXAMPLE_FILE.exists():
        raise SystemExit(".env.example was not found.")

    env_text = ENV_EXAMPLE_FILE.read_text()
    env_text = env_text.replace(
        "FLASK_SECRET_KEY=change-me-in-development",
        f"FLASK_SECRET_KEY={secrets.token_urlsafe(32)}",
    )
    ENV_FILE.write_text(env_text)
    protect_private_file(ENV_FILE)
    print("Created .env from .env.example.")


def read_env_value(name: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text().splitlines():
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


def warn_if_api_key_missing() -> None:
    groq_key = read_env_value("GROQ_API_KEY")
    openai_key = read_env_value("OPENAI_API_KEY")
    other_keys = [
        read_env_value("ANTHROPIC_API_KEY"),
        read_env_value("GOOGLE_API_KEY"),
        read_env_value("MISTRAL_API_KEY"),
        read_env_value("TOGETHER_API_KEY"),
        read_env_value("XAI_API_KEY"),
        read_env_value("DEEPSEEK_API_KEY"),
    ]
    if not any(looks_like_real_api_key(key) for key in [groq_key, openai_key, *other_keys]):
        print()
        print("When the browser opens, choose an AI provider and paste your API key.")
        print()


def start_app(python_path: Path) -> int:
    port = os.getenv("PORT", DEFAULT_PORT)
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.setdefault("PORT", port)
    env.setdefault("FLASK_DEBUG", "false")
    env.setdefault("DELPHIC_TRUSTED_HOSTS", "127.0.0.1,localhost")
    env.setdefault("PYTHONUNBUFFERED", "1")

    print(f"Starting Delphic AI at {url}")
    process = subprocess.Popen([str(python_path), "app.py"], cwd=ROOT, env=env)

    try:
        time.sleep(1.5)
        if process.poll() is not None:
            return process.returncode
        webbrowser.open(url)
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
    python_path = ensure_virtual_environment()
    install_dependencies(python_path)
    ensure_env_file()
    warn_if_api_key_missing()
    return start_app(python_path)


if __name__ == "__main__":
    raise SystemExit(main())
