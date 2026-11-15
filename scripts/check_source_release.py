"""Check an extracted Python ZIP using disposable data and no paid AI calls."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener
import zipfile

try:
    from .check_packaged_library import Browser, MATH, SCIENCE
except ImportError:
    from check_packaged_library import Browser, MATH, SCIENCE


def verify_archive(archive: Path) -> dict:
    checksum = archive.with_suffix(archive.suffix + ".sha256").read_text(encoding="ascii").split()
    if checksum != [hashlib.sha256(archive.read_bytes()).hexdigest(), archive.name]:
        raise ValueError("The archive checksum does not match.")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("The archive has duplicate paths.")
        for entry in bundle.infolist():
            path = PurePosixPath(entry.filename)
            if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                    or str(path) != entry.filename or path.parts[0] != "Delphic AI"
                    or (entry.external_attr >> 16) & 0o170000 != 0o100000):
                raise ValueError("The archive has an unsafe path or non-file entry.")
        manifest = json.loads(bundle.read("Delphic AI/RELEASE_MANIFEST.json"))
        expected = {"Delphic AI/" + name for name in manifest["files"]}
        if set(names) != expected | {"Delphic AI/RELEASE_MANIFEST.json"}:
            raise ValueError("The archive differs from its file manifest.")
        for name, info in manifest["files"].items():
            data = bundle.read("Delphic AI/" + name)
            if len(data) != info["bytes"] or hashlib.sha256(data).hexdigest() != info["sha256"]:
                raise ValueError(f"The manifest hash does not match {name}.")
        if not {"run_app.py", "run_mac.command", "run_windows.bat", ".env.example"} <= manifest["files"].keys():
            raise ValueError("The source download is missing core files.")
    return manifest


def browser(base: str) -> Browser:
    client = Browser(base)
    client.opener = build_opener(ProxyHandler({}), HTTPCookieProcessor())
    return client


def clean_environment(data_dir: Path, port: int) -> dict:
    env = {name: value for name, value in os.environ.items() if not (
        name.endswith("API_KEY") or name.startswith("DELPHIC_") or name.startswith("PIP_")
        or name in {"FLASK_SECRET_KEY", "PYTHONPATH", "PYTHONHOME", "PYTHON_DOTENV_DISABLED"}
    )}
    env.update(
        DELPHIC_DATA_DIR=str(data_dir), DELPHIC_ENV_FILE=str(data_dir / ".env"),
        DELPHIC_OPEN_BROWSER="false", DELPHIC_NO_PAUSE="true", FLASK_DEBUG="false",
        DELPHIC_ENABLE_EXPERIMENTAL_IMAGES="false", PORT=str(port),
        PYTHONUNBUFFERED="1", PIP_CONFIG_FILE=os.devnull,
    )
    # Blank values override the placeholder-only settings created in the temp directory.
    for name in ("GROQ", "OPENAI", "ANTHROPIC", "GOOGLE", "MISTRAL", "TOGETHER", "OPENROUTER", "XAI", "DEEPSEEK"):
        env[name + "_API_KEY"] = ""
    return env


def stop_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        os.killpg(process.pid, signal.SIGINT)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=True, capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


@contextmanager
def running_source(package: Path, directory: Path, port: int):
    env = clean_environment(directory / "data", port)
    flags = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    log_path = directory / "startup.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, str(package / "run_app.py")], cwd=package, env=env,
            stdout=log, stderr=log, **flags,
        )
        try:
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("Source startup failed.\n" + log_path.read_text(encoding="utf-8", errors="replace")[-4000:])
                if "Delphic AI is ready:" in log_path.read_text(encoding="utf-8", errors="replace"):
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Source startup did not finish within 10 minutes.")
            yield
        finally:
            stop_tree(process)
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError("A server remained listening after source shutdown.")


def check(archive: Path, port: int) -> dict:
    manifest = verify_archive(archive)
    # Never test an already-running student app by accident.
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="delphic-source-check-") as name:
        directory = Path(name)
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(directory)
        package = directory / "Delphic AI"
        client = browser(f"http://127.0.0.1:{port}")
        with running_source(package, directory, port):
            for route in ("/", "/science"):
                assert "studyLibraryDialog" in client.request(route)
            for asset in ("script.js", "style.css", "study-library.js", "graphing.js", "science-diagrams.js",
                          "vendor/three/three.module.js", "vendor/katex/katex.min.js", "assets/delphic-logo.png"):
                # Binary assets only need an HTTP-success check, not UTF-8 decoding.
                with client.opener.open(client.base + "/static/" + asset, timeout=15) as response:
                    assert response.status == 200 and response.read(16)
            assert not client.request("/ai-settings")["configured"]
            assert client.request("/ai-settings")["device_storage_available"] is False
            conflict = subprocess.run(
                [sys.executable, str(package / "run_app.py")], cwd=package,
                env=clean_environment(directory / "conflict-data", port),
                capture_output=True, text=True, timeout=150,
            )
            assert conflict.returncode != 0 and "Delphic AI is ready:" not in conflict.stdout
            assert "port is busy" in conflict.stdout
            notes = []
            for subject, text in (("math", MATH), ("science", SCIENCE)):
                assert client.preview("notes.txt", text.encode())["text"] == text
                result = client.request("/library/notes", "POST", {
                    "title": subject + " synthetic notes", "subject": subject, "text": text, "enabled": True,
                }, expected=201)
                notes.append(result["id"])
            assert len(client.request("/library/notes")["notes"]) == 2
            stranger = browser(client.base)
            assert stranger.request("/library/notes")["notes"] == []
            stranger.request("/library/notes/" + notes[0], "DELETE", expected=404)
            graph = client.request("/plot", "POST", {"message": "Graph y = x^(1/3)"})
            assert graph
            client.request("/local-graph-message", "POST", {"message": "Graph y = x^2 - 4"})
            history = client.request("/history")
            assert len(history["messages"]) == 2
            chat = history["session_id"]
            assert stranger.request("/history")["messages"] == []
            secret_hash = hashlib.sha256((directory / "data/.env").read_bytes()).hexdigest()
            stamp_time = (package / ".venv/.requirements.sha256").stat().st_mtime_ns
            print("PASS: extracted pages/assets, occupied-port failure, local graph, saved chat, note import/save and ownership", flush=True)
        with running_source(package, directory, port):
            assert (package / ".venv/.requirements.sha256").stat().st_mtime_ns == stamp_time
            assert hashlib.sha256((directory / "data/.env").read_bytes()).hexdigest() == secret_hash
            assert client.request("/history")["session_id"] == chat
            assert len(client.request("/history")["messages"]) == 2
            assert len(client.request("/library/notes")["notes"]) == 2
            client.request("/library/notes/" + notes[0], "PATCH", {"enabled": False, "title": "Renamed synthetic notes"})
            assert client.request("/library/status?subject=math")["enabled_count"] == 0
            print("PASS: real server restart, environment reuse, retained cookies, stable signing and note editing", flush=True)
        updated = directory / "replacement folder"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(updated)
        with running_source(updated / "Delphic AI", directory, port):
            assert client.request("/history")["session_id"] == chat
            assert len(client.request("/history")["messages"]) == 2
            assert len(client.request("/library/notes")["notes"]) == 2
            for note in notes:
                client.request("/library/notes/" + note, "DELETE")
            assert client.request("/library/notes")["notes"] == []
            client.request("/sessions/delete", "POST", {"session_id": chat})
            assert client.request("/sessions")["sessions"] == []
            print("PASS: replacement app folder preserves saved work; deletion and shutdown succeed", flush=True)
        installed_bytes = sum(path.stat().st_size for path in package.rglob("*") if path.is_file() and not path.is_symlink())
    return {
        "archive": archive.name, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_bytes": archive.stat().st_size, "installed_package_bytes": installed_bytes,
        "version": manifest["version"], "source": manifest["source"],
        "platform": platform.platform(), "architecture": platform.machine(),
        "python": platform.python_version(), "seconds": round(time.monotonic() - started, 2),
        "real_provider_calls": False, "separate_machine_test": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--port", type=int, default=51276)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535.")
    report = check(args.archive.resolve(), args.port)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
