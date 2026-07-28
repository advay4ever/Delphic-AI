"""
Desktop bundle entry point for Delphic AI.

This is for packaged builds that include Python inside the app. Source-code users
should keep using run_app.py, run_mac.command, or run_windows.bat.
"""

from __future__ import annotations

import os
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path

from werkzeug.serving import WSGIRequestHandler, make_server


APP_NAME = "Delphic AI"
DEFAULT_PORT = "5001"


def protect_private_path(path: Path, mode: int) -> None:
    """Restrict local app data to the current account where chmod is supported."""
    if os.name == "nt" or not path.exists():
        return
    try:
        path.chmod(mode)
    except OSError:
        pass


class QuietRequestHandler(WSGIRequestHandler):
    """Avoid writing Flask request logs to a missing macOS app console."""

    def log_request(self, code="-", size="-"):
        pass


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    configured_dir = os.getenv("DELPHIC_DATA_DIR")
    if configured_dir:
        return Path(configured_dir)
    if os.name == "nt":
        base_dir = os.getenv("APPDATA") or str(Path.home())
        return Path(base_dir) / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".local" / "share" / "delphic-ai"


def ensure_env_file(data_dir: Path) -> Path:
    env_file = data_dir / ".env"
    if env_file.exists():
        protect_private_path(env_file, 0o600)
        return env_file

    example_file = bundled_root() / ".env.example"
    if example_file.exists():
        env_text = example_file.read_text()
    else:
        env_text = (
            "GROQ_API_KEY=your-groq-api-key-here\n"
            "OPENAI_API_KEY=your-openai-api-key-here\n"
            "ANTHROPIC_API_KEY=your-anthropic-api-key-here\n"
            "GOOGLE_API_KEY=your-google-api-key-here\n"
            "MISTRAL_API_KEY=your-mistral-api-key-here\n"
            "TOGETHER_API_KEY=your-together-api-key-here\n"
            "XAI_API_KEY=your-xai-api-key-here\n"
            "DEEPSEEK_API_KEY=your-deepseek-api-key-here\n"
            "FLASK_SECRET_KEY=change-me-in-development\n"
        )

    env_text = env_text.replace(
        "FLASK_SECRET_KEY=change-me-in-development",
        f"FLASK_SECRET_KEY={secrets.token_urlsafe(32)}",
    )
    env_file.write_text(env_text)
    protect_private_path(env_file, 0o600)
    return env_file


def start_local_server(flask_app, port: int):
    """Run the local tutor server without blocking the desktop app."""
    server = make_server(
        "127.0.0.1",
        port,
        flask_app,
        request_handler=QuietRequestHandler,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_macos_status_window(url: str, server) -> None:
    """Keep the macOS app responsive while the tutor lives in the browser."""
    import tkinter as tk

    window = tk.Tk()
    window.title(APP_NAME)
    window.geometry("430x210")
    window.resizable(False, False)

    content = tk.Frame(window, padx=28, pady=24)
    content.pack(fill="both", expand=True)
    tk.Label(content, text="Delphic AI is running", font=("Helvetica", 18, "bold")).pack(anchor="w")
    tk.Label(
        content,
        text="Your tutor is open in your web browser. Keep this window open while you use it.",
        justify="left",
        wraplength=360,
    ).pack(anchor="w", pady=(10, 18))
    tk.Button(content, text="Open Delphic AI", command=lambda: webbrowser.open(url)).pack(anchor="w")

    def close_app() -> None:
        server.shutdown()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", close_app)
    window.mainloop()


def main() -> None:
    data_dir = user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    protect_private_path(data_dir, 0o700)
    env_file = ensure_env_file(data_dir)

    os.environ.setdefault("DELPHIC_DATA_DIR", str(data_dir))
    os.environ.setdefault("DELPHIC_ENV_FILE", str(env_file))
    os.environ.setdefault("PORT", DEFAULT_PORT)
    os.environ.setdefault("FLASK_DEBUG", "false")
    os.environ.setdefault("DELPHIC_TRUSTED_HOSTS", "127.0.0.1,localhost")

    from app import app

    port = int(os.getenv("PORT", DEFAULT_PORT))
    url = f"http://127.0.0.1:{port}"
    print(f"Starting {APP_NAME} at {url}")
    print(f"Settings and chat history are stored in: {data_dir}")

    if sys.platform == "darwin":
        server, server_thread = start_local_server(app, port)
        try:
            if os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false":
                time.sleep(0.5)
                webbrowser.open(url)
            run_macos_status_window(url, server)
        finally:
            server.shutdown()
            server_thread.join(timeout=2)
        return

    if os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false":
        time.sleep(0.5)
        webbrowser.open(url)
    app.run(debug=False, port=port, use_reloader=False)


if __name__ == "__main__":
    main()
