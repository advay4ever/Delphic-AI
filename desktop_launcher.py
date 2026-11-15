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

from werkzeug.serving import WSGIRequestHandler, ThreadedWSGIServer
from version import APP_VERSION


APP_NAME = "Delphic AI"
DEFAULT_PORT = "5001"
MAX_DESKTOP_REQUESTS = 8


class DesktopLaunchError(RuntimeError):
    """An expected startup problem that should be explained to the user."""


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


class BoundedDesktopServer(ThreadedWSGIServer):
    """Reserve a worker before spawning a request thread, with a fixed limit."""

    def __init__(self, host, port, application, *, maximum=MAX_DESKTOP_REQUESTS,
                 request_handler=QuietRequestHandler, **kwargs):
        if not 1 <= maximum <= 32:
            raise ValueError("Choose between 1 and 32 desktop request workers.")
        self._workers = threading.BoundedSemaphore(maximum)
        super().__init__(host, port, application, handler=request_handler, **kwargs)

    def process_request(self, request, client_address):
        if not self._workers.acquire(blocking=False):
            body = b'{"error":"Delphic is busy. Please try again shortly."}'
            try:
                request.settimeout(0.2)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: application/json\r\n"
                                b"Cache-Control: no-store\r\nRetry-After: 1\r\nConnection: close\r\n"
                                + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._workers.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._workers.release()


def start_local_server(flask_app, port: int, *, maximum=MAX_DESKTOP_REQUESTS):
    """Run the local tutor server without blocking the desktop app."""
    try:
        server = BoundedDesktopServer(
            "127.0.0.1",
            port,
            flask_app,
            request_handler=QuietRequestHandler,
            maximum=maximum,
        )
    except (OSError, SystemExit) as exc:
        raise DesktopLaunchError(
            f"Delphic AI could not use local port {port}. Close another copy of "
            "Delphic AI, then open the app again."
        ) from exc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def run_macos_status_window(url: str, server) -> None:
    """Keep the macOS app responsive while the tutor lives in the browser."""
    import tkinter as tk

    window = tk.Tk()
    window.title(f"{APP_NAME} {APP_VERSION}")
    window.geometry("430x210")
    window.resizable(False, False)

    content = tk.Frame(window, padx=28, pady=24)
    content.pack(fill="both", expand=True)
    tk.Label(
        content,
        text=f"Delphic AI {APP_VERSION} is running",
        font=("Helvetica", 18, "bold"),
    ).pack(anchor="w")
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


def show_macos_error(message: str) -> None:
    """Show a readable startup error when a packaged Mac app has no console."""
    if os.getenv("DELPHIC_HEADLESS", "false").lower() == "true":
        return
    try:
        import tkinter as tk
        from tkinter import messagebox

        window = tk.Tk()
        window.withdraw()
        messagebox.showerror(f"{APP_NAME} {APP_VERSION}", message, parent=window)
        window.destroy()
    except Exception:
        # The same message has already been printed for logs and Terminal launches.
        pass


def run_headless(server, server_thread: threading.Thread) -> None:
    """Keep a packaged server alive for automated smoke tests."""
    try:
        while server_thread.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server_thread.join(timeout=2)


def main() -> int:
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
    from ai.device_credentials import DeviceCredentialStore, native_backend

    app.extensions["desktop_credentials"] = DeviceCredentialStore(data_dir, native_backend())

    port = int(os.getenv("PORT", DEFAULT_PORT))
    url = f"http://127.0.0.1:{port}"
    print(f"Starting {APP_NAME} at {url}")
    print(f"Settings and chat history are stored in: {data_dir}")

    if sys.platform == "darwin":
        try:
            server, server_thread = start_local_server(app, port)
        except DesktopLaunchError as exc:
            print(str(exc), file=sys.stderr)
            show_macos_error(str(exc))
            return 1
        try:
            if os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false":
                time.sleep(0.5)
                webbrowser.open(url)
            if os.getenv("DELPHIC_HEADLESS", "false").lower() == "true":
                run_headless(server, server_thread)
            else:
                run_macos_status_window(url, server)
        finally:
            server.shutdown()
            server_thread.join(timeout=2)
        return 0

    if os.getenv("DELPHIC_OPEN_BROWSER", "true").lower() != "false":
        time.sleep(0.5)
        webbrowser.open(url)
    app.run(debug=False, port=port, use_reloader=False)
    return 0


if __name__ == "__main__":
    from multiprocessing import freeze_support
    freeze_support()
    raise SystemExit(main())
