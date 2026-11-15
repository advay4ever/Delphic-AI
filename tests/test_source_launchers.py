"""Execute launcher failure paths without touching local data or providers."""

import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "darwin", reason="Native Mac launcher check")
@pytest.mark.parametrize("old_python", [False, True])
def test_mac_launcher_explains_missing_or_unsupported_python(tmp_path, old_python):
    if old_python:
        stub = tmp_path / "python3"
        stub.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo Python 3.9; fi\nexit 1\n')
        stub.chmod(0o755)
    env = {**os.environ, "PATH": str(tmp_path), "DELPHIC_NO_PAUSE": "true"}
    result = subprocess.run(["/bin/zsh", str(ROOT / "run_mac.command")], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 1
    assert "Python 3.10 or newer" in result.stdout
    assert "python.org" in result.stdout


@pytest.mark.skipif(sys.platform != "darwin", reason="Native Mac launcher check")
def test_mac_launcher_handles_a_supported_python_and_a_spaced_folder(tmp_path):
    download = tmp_path / "download with spaces"
    download.mkdir()
    shutil.copyfile(ROOT / "run_mac.command", download / "run_mac.command")
    (download / "run_app.py").write_text('from pathlib import Path\nprint(Path.cwd())\nraise SystemExit(7)\n')
    executable = tmp_path / "python3"
    executable.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    executable.chmod(0o755)
    result = subprocess.run(["/bin/zsh", str(download / "run_mac.command")],
                            env={**os.environ, "PATH": str(tmp_path), "DELPHIC_NO_PAUSE": "true"},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 7
    assert str(download) in result.stdout
    assert "stopped with an error" in result.stdout


@pytest.mark.skipif(os.name != "nt", reason="Must execute Windows cmd.exe, not emulate it")
@pytest.mark.parametrize("selected", [None, "py", "python", "python3"])
def test_windows_launcher_checks_interpreters_and_preserves_exit_status(tmp_path, selected):
    download = tmp_path / "download with spaces"
    download.mkdir()
    shutil.copyfile(ROOT / "run_windows.bat", download / "run_windows.bat")
    (download / "run_app.py").write_text("# must not run real app")
    (download / "requirements.txt").write_text("# fixture")
    for name in ("py", "python", "python3"):
        text = "@echo off\nexit /b 1\n"
        if name == selected:
            text = '@echo off\nif "%1"=="-3" shift\nif "%1"=="-I" exit /b 0\necho SYNTHETIC_APP\nexit /b 7\n'
        (download / (name + ".cmd")).write_text(text)
    env = {**os.environ, "PATH": str(download), "DELPHIC_NO_PAUSE": "true"}
    result = subprocess.run([os.environ["COMSPEC"], "/d", "/c", "run_windows.bat"], cwd=download,
                            env=env, capture_output=True, text=True, timeout=20)
    if selected is None:
        assert result.returncode == 1
        assert "needs a working Python" in result.stdout
    else:
        assert result.returncode == 7
        assert "SYNTHETIC_APP" in result.stdout
