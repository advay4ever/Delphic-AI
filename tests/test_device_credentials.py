from types import SimpleNamespace

import pytest

import app as app_module
from ai import device_credentials as vault
from images.providers import OPENROUTER_IMAGE_MODEL


KEY = "gsk-device-test-only-not-a-real-key"
CONFIG = {"provider": "groq", "api_key": KEY, "model": "llama-3.1-8b-instant",
          "image_model": OPENROUTER_IMAGE_MODEL}


class FakeVault:
    def __init__(self):
        self.values = {}
        self.failure = None
        self.reads = 0

    def get_password(self, service, account):
        self.reads += 1
        if self.failure == "read":
            raise RuntimeError(KEY)
        return self.values.get((service, account))

    def set_password(self, service, account, password):
        if self.failure == "save":
            raise RuntimeError(KEY)
        self.values[service, account] = password

    def delete_password(self, service, account):
        if self.failure == "delete":
            raise RuntimeError(KEY)
        self.values.pop((service, account), None)


@pytest.fixture
def desktop(monkeypatch, tmp_path):
    backend = FakeVault()
    store = vault.DeviceCredentialStore(tmp_path, backend)
    monkeypatch.setitem(app_module.app.extensions, "desktop_credentials", store)
    monkeypatch.setattr(app_module, "get_default_provider_config", lambda: None)
    app_module.AI_SETTINGS_BY_SESSION.clear()
    app_module.AI_SETTINGS_REVOKED_IDS.clear()
    yield app_module.app.test_client(), store, backend
    app_module.AI_SETTINGS_BY_SESSION.clear()
    app_module.AI_SETTINGS_REVOKED_IDS.clear()


def test_remembered_connection_survives_new_store_and_session(desktop, monkeypatch, tmp_path):
    client, store, backend = desktop
    response = client.post("/ai-settings", json={**CONFIG, "remember_key": True})
    assert response.status_code == 200
    assert response.json["remember_key"] is True
    assert KEY not in response.text
    assert {p.name for p in tmp_path.iterdir()} == {"chat_history.db"}
    assert KEY.encode() not in (tmp_path / "chat_history.db").read_bytes()
    with client.session_transaction() as cookie:
        assert KEY not in str(dict(cookie))
    app_module.AI_SETTINGS_BY_SESSION.clear()
    monkeypatch.setitem(app_module.app.extensions, "desktop_credentials", vault.DeviceCredentialStore(tmp_path, backend))
    response = app_module.app.test_client().get("/ai-settings")
    assert response.json["configured"] is True
    assert response.json["source"] == "device"
    assert response.json["model"] == CONFIG["model"]
    assert KEY not in response.text


def test_temporary_default_never_writes_the_vault(desktop):
    client, store, backend = desktop
    response = client.post("/ai-settings", json=CONFIG)
    assert response.status_code == 200
    assert response.json["remember_key"] is False
    assert backend.values == {}


def test_unchecking_removes_saved_copy_but_keeps_current_connection(desktop):
    client, store, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": True}).status_code == 200
    response = client.post("/ai-settings", json={**CONFIG, "api_key": "", "remember_key": False})
    assert response.status_code == 200
    assert response.json["configured"] is True
    assert response.json["remember_key"] is False
    assert backend.values == {}
    app_module.AI_SETTINGS_BY_SESSION.clear()
    assert client.get("/ai-settings").json["configured"] is False


def test_model_only_update_preserves_remembered_key(desktop):
    client, store, _ = desktop
    store.save(CONFIG)
    response = client.post("/ai-settings", json={"provider": "groq", "model": "openai/gpt-oss-20b"})
    assert response.status_code == 200
    assert response.json["remember_key"] is True
    assert store.load()["model"] == "openai/gpt-oss-20b"


def test_model_save_cannot_restore_a_key_forgotten_during_validation(desktop, monkeypatch):
    client, store, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": True}).status_code == 200
    def forget_before_commit(*_):
        store.clear()
        app_module.forget_temporary_ai_config()
        return None
    monkeypatch.setattr(app_module, "get_model_validation_error", forget_before_commit)
    response = client.post("/ai-settings", json={"provider": "groq", "model": "openai/gpt-oss-20b", "remember_key": True})
    assert response.status_code == 409
    assert backend.values == {}
    assert not app_module.AI_SETTINGS_BY_SESSION


def test_forgetting_removes_saved_and_temporary_copies(desktop):
    client, store, backend = desktop
    client.post("/ai-settings", json={**CONFIG, "remember_key": True})
    response = client.delete("/ai-settings")
    assert response.status_code == 200
    assert response.json["configured"] is False
    assert response.json["has_saved_key"] is False
    assert backend.values == {}
    assert not app_module.AI_SETTINGS_BY_SESSION


@pytest.mark.parametrize("operation", ["save", "delete"])
def test_vault_failures_do_not_claim_success_or_change_active_key(desktop, operation, caplog):
    client, store, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": True}).status_code == 200
    backend.failure = operation
    if operation == "delete":
        response = client.delete("/ai-settings")
    else:
        response = client.post("/ai-settings", json={**CONFIG, "api_key": KEY + "-replacement", "remember_key": True})
    assert response.status_code == 503
    assert store.load()["api_key"] == KEY
    with client.session_transaction() as cookie:
        assert app_module.get_temporary_ai_config(cookie["ai_settings_id"])["api_key"] == KEY
    assert KEY not in response.text + caplog.text


def test_unavailable_backend_still_allows_temporary_connection(desktop):
    client, store, backend = desktop
    store.backend = None
    response = client.post("/ai-settings", json={**CONFIG, "remember_key": True})
    assert response.status_code == 503
    assert not app_module.AI_SETTINGS_BY_SESSION
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": False}).status_code == 200
    assert client.get("/ai-settings").json["device_storage_available"] is False


def test_partially_failed_native_replace_does_not_claim_the_key_is_remembered(desktop, monkeypatch):
    client, store, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": True}).status_code == 200
    def fail_after_removing_old(*_):
        backend.values.clear()
        raise RuntimeError(KEY)
    monkeypatch.setattr(backend, "set_password", fail_after_removing_old)
    response = client.post("/ai-settings", json={**CONFIG, "api_key": KEY + "-new", "remember_key": True})
    assert response.status_code == 503
    status = client.get("/ai-settings").json
    assert status["configured"] is True
    assert status["remember_key"] is False
    assert status["device_storage_error"]
    assert KEY not in response.text


def test_forget_retry_recovers_when_native_delete_completed_before_failure(desktop, monkeypatch):
    client, store, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": True}).status_code == 200
    def delete_then_fail(*_):
        backend.values.clear()
        raise RuntimeError(KEY)
    monkeypatch.setattr(backend, "delete_password", delete_then_fail)
    assert client.delete("/ai-settings").status_code == 503
    response = client.delete("/ai-settings")
    assert response.status_code == 200
    assert response.json["configured"] is False
    assert response.json["has_saved_key"] is False


@pytest.mark.parametrize("raw", ["not-json", "[]", '{"version":2}', '{"version":1,"api_key":42}'])
def test_corrupt_vault_record_is_not_used_or_exposed(desktop, raw):
    client, store, backend = desktop
    backend.values[store.service, store.account] = raw
    status = client.get("/ai-settings").json
    assert status["configured"] is False
    assert status["device_storage_error"]
    assert status["can_forget"] is True
    assert client.delete("/ai-settings").status_code == 200
    assert not backend.values


def test_locked_vault_read_is_not_repeated_on_every_request(desktop, caplog):
    client, store, backend = desktop
    backend.failure = "read"
    for _ in range(3):
        response = client.get("/ai-settings")
        assert response.json["device_storage_error"]
        assert KEY not in response.text
    assert backend.reads == 1
    assert KEY not in caplog.text


def test_obsolete_saved_model_is_not_used(desktop):
    client, store, _ = desktop
    store.save({**CONFIG, "model": "not-a-listed-model"})
    response = client.get("/ai-settings")
    assert response.json["configured"] is False
    assert response.json["has_saved_key"] is True
    assert "no longer supported" in response.json["device_storage_error"]


@pytest.mark.parametrize("origin", ["https://evil.example", "null"])
@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_cross_origin_requests_cannot_read_use_or_change_vault(desktop, origin, method):
    client, store, backend = desktop
    response = getattr(client, method)("/ai-settings", headers={"Origin": origin})
    assert response.status_code == 403
    assert backend.reads == 0


def test_remote_client_cannot_access_desktop_vault(desktop):
    client, store, backend = desktop
    response = client.get("/ai-settings", environ_overrides={"REMOTE_ADDR": "192.0.2.10"})
    assert response.status_code == 403
    assert backend.reads == 0


def test_website_cannot_enable_device_storage(monkeypatch):
    monkeypatch.delitem(app_module.app.extensions, "desktop_credentials", raising=False)
    client = app_module.app.test_client()
    response = client.post("/ai-settings", json={**CONFIG, "remember_key": True})
    assert response.status_code == 400
    assert client.get("/ai-settings").json["device_storage"] is False


@pytest.mark.parametrize("value", ["true", 1, None, []])
def test_remember_flag_requires_boolean(desktop, value):
    client, _, backend = desktop
    assert client.post("/ai-settings", json={**CONFIG, "remember_key": value}).status_code == 400
    assert not backend.values


def test_invalid_model_is_not_persisted(desktop):
    client, _, backend = desktop
    response = client.post("/ai-settings", json={**CONFIG, "model": "bad", "remember_key": True})
    assert response.status_code == 400
    assert not backend.values


def test_vault_names_are_scoped_to_installation_data(tmp_path):
    backend = FakeVault()
    first = vault.DeviceCredentialStore(tmp_path / "one", backend)
    second = vault.DeviceCredentialStore(tmp_path / "two", backend)
    first.save(CONFIG)
    assert second.load() is None
    assert KEY not in first.service


def test_oversized_connection_fails_before_native_write(tmp_path):
    backend = FakeVault()
    store = vault.DeviceCredentialStore(tmp_path, backend)
    with pytest.raises(vault.DeviceCredentialError, match="too large"):
        store.save({**CONFIG, "api_key": "a" * 2000})
    assert backend.values == {}


@pytest.mark.parametrize("platform, module, name", [
    ("darwin", "keyring.backends.macOS", "Keyring"),
    ("win32", "keyring.backends.Windows", "WinVaultKeyring"),
])
def test_only_explicit_native_backends_are_selected(monkeypatch, platform, module, name):
    monkeypatch.setattr(vault.sys, "platform", platform)
    imports = []
    backend = SimpleNamespace(priority=5)
    def load(path):
        imports.append(path)
        return SimpleNamespace(**{name: lambda: backend})
    monkeypatch.setattr(vault.importlib, "import_module", load)
    assert vault.native_backend() is backend
    assert imports == [module]
    if platform == "win32":
        assert backend.persist == "local machine"


def test_missing_package_never_falls_back_to_file_storage(monkeypatch):
    monkeypatch.setattr(vault.sys, "platform", "darwin")
    def missing(_):
        raise ImportError("not installed")
    monkeypatch.setattr(vault.importlib, "import_module", missing)
    assert vault.native_backend() is None
