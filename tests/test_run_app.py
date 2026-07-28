from pathlib import Path

import run_app


def test_macos_source_launcher_uses_application_support(monkeypatch, tmp_path):
    monkeypatch.delenv("DELPHIC_DATA_DIR", raising=False)
    monkeypatch.setattr(run_app.os, "name", "posix")
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

        def poll(self):
            return None

        def wait(self, timeout=None):
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

    assert run_app.start_app(python_path, data_dir, env_file) == 0
    assert captured["env"]["DELPHIC_DATA_DIR"] == str(data_dir)
    assert captured["env"]["DELPHIC_ENV_FILE"] == str(env_file)
