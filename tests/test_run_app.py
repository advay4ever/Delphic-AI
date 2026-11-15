from pathlib import Path
import json
import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import run_app


def test_macos_source_launcher_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.delenv("DELPHIC_DATA_DIR", raising=False)
    monkeypatch.setattr(run_app, "os", SimpleNamespace(name="posix", getenv=os.getenv))
    monkeypatch.setattr(run_app.sys, "platform", "darwin")
    monkeypatch.setattr(run_app.Path, "home", classmethod(lambda cls: tmp_path))

    assert run_app.user_data_dir() == (
        tmp_path / "Library" / "Application Support" / "Delphic AI"
    )


def test_configured_data_directory_takes_priority(monkeypatch, tmp_path):
    configured_dir = tmp_path / "custom-data"
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(configured_dir))

    assert run_app.user_data_dir() == configured_dir


def test_ensure_env_file_creates_private_settings(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    example_file = project_dir / ".env.example"
    example_file.write_text(
        "OPENAI_API_KEY=your-openai-api-key-here\n"
        "FLASK_SECRET_KEY=change-me-in-development\n"
    )
    data_dir = tmp_path / "data"
    monkeypatch.setattr(run_app, "ROOT", project_dir)
    monkeypatch.setattr(run_app, "ENV_EXAMPLE_FILE", example_file)

    env_file = run_app.ensure_env_file(data_dir)

    assert env_file == data_dir / ".env"
    assert "change-me-in-development" not in env_file.read_text()
    assert "OPENAI_API_KEY=your-openai-api-key-here" in env_file.read_text()


def test_ensure_env_file_migrates_existing_project_settings(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    legacy_env = project_dir / ".env"
    legacy_env.write_text("OPENAI_API_KEY=test-value\n")
    data_dir = tmp_path / "data"
    monkeypatch.setattr(run_app, "ROOT", project_dir)

    env_file = run_app.ensure_env_file(data_dir)

    assert env_file.read_text() == legacy_env.read_text()
    assert legacy_env.exists()


def test_start_app_passes_private_data_paths_to_app(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        returncode = 0
        done = False

        def poll(self):
            return 0 if self.done else None

        def wait(self, timeout=None):
            self.done = True
            return 0

    def fake_popen(command, cwd, env):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["env"] = env
        return FakeProcess()

    data_dir = tmp_path / "data"
    env_file = data_dir / ".env"
    python_path = tmp_path / "python"
    monkeypatch.setenv("DELPHIC_OPEN_BROWSER", "false")
    monkeypatch.setattr(run_app.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(run_app.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(run_app, "app_is_ready", lambda _port, _token: True)

    assert run_app.start_app(python_path, data_dir, env_file) == 0
    assert captured["env"]["DELPHIC_DATA_DIR"] == str(data_dir)
    assert captured["env"]["DELPHIC_ENV_FILE"] == str(env_file)
    assert captured["env"]["FLASK_DEBUG"] == "false"
    assert len(captured["env"]["DELPHIC_STARTUP_TOKEN"]) >= 32


@pytest.fixture
def local_environment(monkeypatch, tmp_path):
    root = tmp_path / "download with spaces"
    root.mkdir()
    environment = root / ".venv"
    monkeypatch.setattr(run_app, "ROOT", root)
    monkeypatch.setattr(run_app, "VENV_DIR", environment)
    monkeypatch.setattr(run_app, "REQUIREMENTS_FILE", root / "requirements.txt")
    monkeypatch.setattr(run_app, "REQUIREMENTS_STAMP", environment / ".requirements.sha256")
    return environment


def test_creates_and_checks_an_isolated_environment(monkeypatch, local_environment):
    def create(path, with_pip):
        assert path == local_environment
        assert with_pip
        path.mkdir()

    monkeypatch.setattr(run_app.venv, "create", create)
    probe = Mock(return_value=SimpleNamespace(stdout=json.dumps({
        "prefix": str(local_environment), "base": "/system/python", "version": [3, 13],
    })))
    monkeypatch.setattr(run_app.subprocess, "run", probe)
    assert run_app.ensure_virtual_environment() == run_app.venv_python()
    assert probe.call_args.kwargs["timeout"] == 15


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired("python", 15), ValueError()])
def test_broken_environment_is_not_deleted(monkeypatch, local_environment, failure):
    local_environment.mkdir()
    sentinel = local_environment / "keep.txt"
    sentinel.write_text("do not delete")
    monkeypatch.setattr(run_app.subprocess, "run", Mock(side_effect=failure))
    with pytest.raises(run_app.LauncherError, match="rename only .venv"):
        run_app.ensure_virtual_environment()
    assert sentinel.read_text() == "do not delete"


@pytest.mark.parametrize("info", [
    {"prefix": "/system", "base": "/system", "version": [3, 13]},
    {"prefix": "moved", "base": "base", "version": [3, 13]},
    {"prefix": "local", "base": "base", "version": [3, 9]},
    {},
])
def test_rejects_wrong_or_old_environment(monkeypatch, local_environment, info):
    local_environment.mkdir()
    if info.get("prefix") == "local":
        info["prefix"] = str(local_environment)
    monkeypatch.setattr(run_app.subprocess, "run", Mock(return_value=SimpleNamespace(stdout=json.dumps(info))))
    with pytest.raises(run_app.LauncherError, match="incomplete or broken"):
        run_app.ensure_virtual_environment()


def test_reuses_only_a_healthy_matching_environment(monkeypatch, local_environment):
    local_environment.mkdir()
    run_app.REQUIREMENTS_FILE.write_text("flask==3.1.3\n")
    run_app.REQUIREMENTS_STAMP.write_text(run_app.sha256(run_app.REQUIREMENTS_FILE))
    monkeypatch.setattr(run_app, "dependencies_healthy", lambda _python: True)
    installer = Mock()
    monkeypatch.setattr(run_app, "run", installer)
    run_app.install_dependencies(run_app.venv_python())
    installer.assert_not_called()


def test_repairs_packages_despite_an_unchanged_stamp(monkeypatch, local_environment):
    local_environment.mkdir()
    run_app.REQUIREMENTS_FILE.write_text("flask==3.1.3\n")
    current_hash = run_app.sha256(run_app.REQUIREMENTS_FILE)
    run_app.REQUIREMENTS_STAMP.write_text(current_hash)
    monkeypatch.setattr(run_app, "dependencies_healthy", Mock(side_effect=[False, True]))
    installer = Mock()
    monkeypatch.setattr(run_app, "run", installer)
    run_app.install_dependencies(run_app.venv_python())
    assert "--force-reinstall" in installer.call_args.args[0]
    assert run_app.REQUIREMENTS_STAMP.read_text().strip() == current_hash


def test_failed_install_does_not_leave_a_success_stamp(monkeypatch, local_environment):
    local_environment.mkdir()
    run_app.REQUIREMENTS_FILE.write_text("flask==3.1.3\n")
    run_app.REQUIREMENTS_STAMP.write_text("stale")
    monkeypatch.setattr(run_app, "run", Mock(side_effect=subprocess.CalledProcessError(1, "pip")))
    with pytest.raises(subprocess.CalledProcessError):
        run_app.install_dependencies(run_app.venv_python())
    assert not run_app.REQUIREMENTS_STAMP.exists()


def test_unhealthy_install_does_not_leave_a_success_stamp(monkeypatch, local_environment):
    local_environment.mkdir()
    run_app.REQUIREMENTS_FILE.write_text("flask==3.1.3\n")
    monkeypatch.setattr(run_app, "run", Mock())
    monkeypatch.setattr(run_app, "dependencies_healthy", lambda _python: False)
    with pytest.raises(run_app.LauncherError, match="libraries did not pass"):
        run_app.install_dependencies(run_app.venv_python())
    assert not run_app.REQUIREMENTS_STAMP.exists()


@pytest.mark.parametrize("returncode", [0, 1])
def test_package_health_checks_include_transitive_dependencies(monkeypatch, returncode):
    runner = Mock(return_value=SimpleNamespace(returncode=returncode))
    monkeypatch.setattr(run_app.subprocess, "run", runner)
    assert run_app.dependencies_healthy(Path("python")) is (returncode == 0)
    if returncode == 0:
        assert "check" in runner.call_args.args[0]


@pytest.mark.parametrize("from_environment", [False, True])
def test_openrouter_is_recognized_without_printing_a_key(monkeypatch, tmp_path, capsys, from_environment):
    for name in run_app.PROVIDER_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / "settings.env"
    fake_key = "test-only-openrouter-credential"
    env_file.write_text("" if from_environment else f"OPENROUTER_API_KEY={fake_key}\n")
    if from_environment:
        monkeypatch.setenv("OPENROUTER_API_KEY", fake_key)
    run_app.warn_if_api_key_missing(env_file)
    assert capsys.readouterr().out == ""


def test_placeholders_still_get_setup_instructions(monkeypatch, tmp_path, capsys):
    for name in run_app.PROVIDER_KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / "settings.env"
    env_file.write_text("OPENROUTER_API_KEY=your-openrouter-api-key-here\n")
    run_app.warn_if_api_key_missing(env_file)
    assert "choose an AI provider" in capsys.readouterr().out


def fake_child():
    child = Mock()
    child.poll.return_value = None
    child.wait.side_effect = lambda **_kwargs: setattr(child.poll, "return_value", 0) or 0
    return child


def test_browser_waits_for_this_servers_readiness(monkeypatch, tmp_path):
    child = fake_child()
    monkeypatch.setattr(run_app.subprocess, "Popen", Mock(return_value=child))
    probes = Mock(side_effect=[False, False, True])
    monkeypatch.setattr(run_app, "app_is_ready", probes)
    monkeypatch.setattr(run_app.time, "sleep", lambda _seconds: None)
    monkeypatch.setenv("DELPHIC_OPEN_BROWSER", "true")
    monkeypatch.setenv("PORT", "5039")
    browser = Mock(return_value=True)
    monkeypatch.setattr(run_app.webbrowser, "open", browser)
    assert run_app.start_app(Path("python"), tmp_path, tmp_path / ".env") == 0
    assert probes.call_count == 3
    browser.assert_called_once_with("http://127.0.0.1:5039")


def test_early_exit_never_opens_a_browser(monkeypatch, tmp_path):
    child = fake_child()
    child.poll.return_value = 1
    monkeypatch.setattr(run_app.subprocess, "Popen", Mock(return_value=child))
    browser = Mock()
    monkeypatch.setattr(run_app.webbrowser, "open", browser)
    with pytest.raises(run_app.LauncherError, match="port is busy"):
        run_app.start_app(Path("python"), tmp_path, tmp_path / ".env")
    browser.assert_not_called()


def test_readiness_timeout_stops_child_without_opening_browser(monkeypatch, tmp_path):
    child = fake_child()
    monkeypatch.setattr(run_app.subprocess, "Popen", Mock(return_value=child))
    monkeypatch.setattr(run_app, "app_is_ready", lambda *_args: False)
    monkeypatch.setattr(run_app, "STARTUP_TIMEOUT_SECONDS", 0)
    browser = Mock()
    monkeypatch.setattr(run_app.webbrowser, "open", browser)
    with pytest.raises(run_app.LauncherError, match="did not become ready"):
        run_app.start_app(Path("python"), tmp_path, tmp_path / ".env")
    child.terminate.assert_called_once()
    browser.assert_not_called()


def test_interrupt_stops_the_child(monkeypatch, tmp_path):
    child = fake_child()
    monkeypatch.setattr(run_app.subprocess, "Popen", Mock(return_value=child))
    monkeypatch.setattr(run_app, "app_is_ready", Mock(side_effect=KeyboardInterrupt))
    assert run_app.start_app(Path("python"), tmp_path, tmp_path / ".env") == 0
    child.terminate.assert_called_once()


def test_hung_child_is_killed_and_reaped():
    child = fake_child()
    child.wait.side_effect = [subprocess.TimeoutExpired("app", 10), 0]
    run_app.stop_process(child)
    child.kill.assert_called_once()
    assert child.wait.call_count == 2


@pytest.mark.parametrize("port", ["zero", "0", "-1", "65536"])
def test_bad_port_is_rejected_before_starting_python(monkeypatch, tmp_path, port):
    monkeypatch.setenv("PORT", port)
    popen = Mock()
    monkeypatch.setattr(run_app.subprocess, "Popen", popen)
    with pytest.raises(run_app.LauncherError, match="PORT must"):
        run_app.start_app(Path("python"), tmp_path, tmp_path / ".env")
    popen.assert_not_called()


@pytest.mark.parametrize("response_token,status,expected", [("nonce", 204, True), ("other", 204, False), ("nonce", 200, False)])
def test_readiness_requires_matching_identity(monkeypatch, response_token, status, expected):
    connection = Mock()
    connection.getresponse.return_value = SimpleNamespace(status=status, getheader=lambda _name: response_token)
    monkeypatch.setattr(run_app.http.client, "HTTPConnection", Mock(return_value=connection))
    assert run_app.app_is_ready(5001, "nonce") is expected
    connection.close.assert_called_once()


def test_ready_endpoint_is_private_to_a_launcher(monkeypatch):
    from app import app
    client = app.test_client()
    monkeypatch.delenv("DELPHIC_STARTUP_TOKEN", raising=False)
    assert client.get("/_launcher/ready").status_code == 404
    monkeypatch.setenv("DELPHIC_STARTUP_TOKEN", "unit-test-nonce")
    assert client.get("/_launcher/ready").status_code == 404
    assert client.get("/_launcher/ready", headers={"X-Delphic-Launcher": "wrong"}).status_code == 404
    response = client.get("/_launcher/ready", headers={"X-Delphic-Launcher": "unit-test-nonce"})
    assert response.status_code == 204
    assert response.headers["X-Delphic-Launcher"] == "unit-test-nonce"
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("version", [(3, 9, 9), (3, 10, 0), (3, 13, 6)])
def test_minimum_python_version(monkeypatch, version):
    monkeypatch.setattr(run_app, "sys", SimpleNamespace(version_info=version))
    if version < (3, 10):
        with pytest.raises(SystemExit, match="needs Python 3.10"):
            run_app.ensure_supported_python()
    else:
        run_app.ensure_supported_python()


def test_windows_data_path_uses_appdata_without_changing_pathlib(monkeypatch, tmp_path):
    monkeypatch.delenv("DELPHIC_DATA_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setattr(run_app, "os", SimpleNamespace(name="nt", getenv=os.getenv))
    assert run_app.user_data_dir() == tmp_path / "Roaming" / "Delphic AI"


def test_main_handles_permission_errors_without_a_traceback(monkeypatch, tmp_path, capsys):
    (tmp_path / "app.py").write_text("")
    (tmp_path / "requirements.txt").write_text("")
    monkeypatch.setattr(run_app, "ROOT", tmp_path)
    monkeypatch.setattr(run_app, "REQUIREMENTS_FILE", tmp_path / "requirements.txt")
    monkeypatch.setattr(run_app, "ensure_virtual_environment", Mock(side_effect=PermissionError))
    assert run_app.main() == 1
    output = capsys.readouterr().out
    assert "writable folder" in output
    assert "Traceback" not in output


def test_main_rejects_incomplete_download_before_creating_an_environment(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(run_app, "ROOT", tmp_path)
    probe = Mock()
    monkeypatch.setattr(run_app, "ensure_virtual_environment", probe)
    assert run_app.main() == 1
    probe.assert_not_called()
    assert "Extract the entire ZIP" in capsys.readouterr().out
