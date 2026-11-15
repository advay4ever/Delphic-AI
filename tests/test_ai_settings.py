import logging

import pytest

import app as app_module
from images.providers import OPENROUTER_IMAGE_MODEL, OPENROUTER_IMAGE_MODELS


TEST_API_KEY = "gsk-phase-three-test-key-that-is-long-enough"


@pytest.fixture(autouse=True)
def clear_temporary_ai_settings():
    app_module.AI_SETTINGS_BY_SESSION.clear()
    app_module.AI_SETTINGS_REVOKED_IDS.clear()
    yield
    app_module.AI_SETTINGS_BY_SESSION.clear()
    app_module.AI_SETTINGS_REVOKED_IDS.clear()


def disable_environment_key(monkeypatch):
    monkeypatch.setattr(app_module, "get_default_provider_config", lambda: None)


def save_test_key(client, model="llama-3.1-8b-instant"):
    return client.post("/ai-settings", json={
        "provider": "groq",
        "api_key": TEST_API_KEY,
        "model": model,
    })


def assert_key_is_not_public(response):
    assert TEST_API_KEY not in response.get_data(as_text=True)
    data = response.get_json()
    assert "api_key" not in data


def test_status_does_not_create_a_settings_cookie_or_return_a_key(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()

    response = client.get("/ai-settings")

    assert response.status_code == 200
    assert response.get_json()["configured"] is False
    assert response.get_json()["can_forget"] is False
    assert response.get_json()["image_model"] == OPENROUTER_IMAGE_MODEL
    assert response.get_json()["image_models"] == list(OPENROUTER_IMAGE_MODELS)
    assert "Set-Cookie" not in response.headers
    assert_key_is_not_public(response)


def test_saved_key_is_server_side_and_status_is_safe(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()

    response = save_test_key(client)

    assert response.status_code == 200
    assert response.get_json()["source"] == "session"
    assert response.get_json()["can_forget"] is True
    assert_key_is_not_public(response)
    with client.session_transaction() as browser_session:
        settings_id = browser_session["ai_settings_id"]
        assert TEST_API_KEY not in str(dict(browser_session))
    assert app_module.AI_SETTINGS_BY_SESSION[settings_id]["api_key"] == TEST_API_KEY

    status_response = client.get("/ai-settings")
    assert status_response.get_json()["provider"] == "groq"
    assert status_response.get_json()["model"] == "llama-3.1-8b-instant"
    assert_key_is_not_public(status_response)


def test_math_and_science_pages_share_one_settings_id(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    assert save_test_key(client).status_code == 200

    assert client.get("/").status_code == 200
    assert client.get("/science").status_code == 200

    with client.session_transaction() as browser_session:
        assert browser_session["session_id"]
        assert browser_session["science_session_id"].startswith("science:")
        settings_id = browser_session["ai_settings_id"]
    assert app_module.get_temporary_ai_config(settings_id, touch=False)["api_key"] == TEST_API_KEY


def test_same_provider_model_can_change_without_resending_key(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    assert save_test_key(client).status_code == 200

    response = client.post("/ai-settings", json={
        "provider": "groq",
        "api_key": "",
        "model": "openai/gpt-oss-20b",
    })

    assert response.status_code == 200
    assert response.get_json()["model"] == "openai/gpt-oss-20b"
    assert_key_is_not_public(response)
    with client.session_transaction() as browser_session:
        settings_id = browser_session["ai_settings_id"]
    assert app_module.AI_SETTINGS_BY_SESSION[settings_id]["api_key"] == TEST_API_KEY


def test_switching_provider_without_a_new_key_keeps_old_settings(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    assert save_test_key(client).status_code == 200

    response = client.post("/ai-settings", json={
        "provider": "openai",
        "api_key": "",
        "model": "gpt-5",
    })

    assert response.status_code == 400
    assert response.get_json()["error"] == "Paste an API key for the selected provider."
    status = client.get("/ai-settings").get_json()
    assert status["provider"] == "groq"
    assert status["model"] == "llama-3.1-8b-instant"


def test_forget_removes_key_and_revokes_old_settings_id(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    assert save_test_key(client).status_code == 200
    with client.session_transaction() as browser_session:
        old_settings_id = browser_session["ai_settings_id"]

    response = client.delete("/ai-settings")

    assert response.status_code == 200
    assert response.get_json()["configured"] is False
    assert response.get_json()["can_forget"] is False
    assert old_settings_id not in app_module.AI_SETTINGS_BY_SESSION
    assert old_settings_id in app_module.AI_SETTINGS_REVOKED_IDS
    assert app_module.get_temporary_ai_config(old_settings_id) is None
    with client.session_transaction() as browser_session:
        assert "ai_settings_id" not in browser_session
    assert_key_is_not_public(response)


def test_inactive_temporary_key_expires(monkeypatch):
    disable_environment_key(monkeypatch)
    monkeypatch.setattr(app_module, "AI_SETTINGS_TTL_SECONDS", 60)
    app_module.AI_SETTINGS_BY_SESSION["expired-id"] = {
        "provider": "groq",
        "api_key": TEST_API_KEY,
        "model": "llama-3.1-8b-instant",
        "last_used_at": 10.0,
    }
    monkeypatch.setattr(app_module.time, "monotonic", lambda: 71.0)

    assert app_module.get_temporary_ai_config("expired-id") is None
    assert "expired-id" not in app_module.AI_SETTINGS_BY_SESSION


def test_environment_status_cannot_be_forgotten_from_the_browser(monkeypatch):
    monkeypatch.setattr(app_module, "get_default_provider_config", lambda: {
        "provider": "groq",
        "api_key": TEST_API_KEY,
        "model": "openai/gpt-oss-120b",
        "source": "env",
    })
    client = app_module.app.test_client()

    response = client.get("/ai-settings")

    assert response.get_json()["configured"] is True
    assert response.get_json()["source"] == "env"
    assert response.get_json()["can_forget"] is False
    assert_key_is_not_public(response)


def test_top_level_localhost_navigation_redirects_to_canonical_address():
    client = app_module.app.test_client()

    response = client.get(
        "/science?topic=forces",
        headers={"Host": "localhost:5001", "Sec-Fetch-Mode": "navigate"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "http://127.0.0.1:5001/science?topic=forces"

    api_response = client.get("/ai-settings", headers={"Host": "localhost:5001"})
    assert api_response.status_code == 200


def test_api_key_is_not_written_to_application_logs(monkeypatch, caplog):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()

    with caplog.at_level(logging.DEBUG):
        response = save_test_key(client)
        client.get("/ai-settings")

    assert response.status_code == 200
    assert TEST_API_KEY not in caplog.text


def test_openrouter_is_available_without_exposing_its_key(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    openrouter_key = "sk-or-v1-test-key-that-is-long-enough"

    response = client.post("/ai-settings", json={
        "provider": "openrouter",
        "api_key": openrouter_key,
        "model": "openai/gpt-5.6-terra",
    })

    assert response.status_code == 200
    data = response.get_json()
    assert data["provider"] == "openrouter"
    assert data["model"] == "openai/gpt-5.6-terra"
    assert openrouter_key not in response.get_data(as_text=True)
    option = next(item for item in data["providers"] if item["id"] == "openrouter")
    assert option["models"] == [{
        "id": "openai/gpt-5.6-terra",
        "label": "GPT-5.6 Terra (recommended)",
    }]


def test_openrouter_image_model_is_saved_and_returned_without_the_key(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()
    flare_model = "openai/gpt-image-2.5-flare"

    response = client.post("/ai-settings", json={
        "provider": "openrouter",
        "api_key": "sk-or-v1-test-key-that-is-long-enough",
        "model": "openai/gpt-5.6-terra",
        "image_model": flare_model,
    })

    assert response.status_code == 200
    assert response.get_json()["image_model"] == flare_model
    assert "api_key" not in response.get_json()
    with client.session_transaction() as browser_session:
        settings_id = browser_session["ai_settings_id"]
    assert app_module.AI_SETTINGS_BY_SESSION[settings_id]["image_model"] == flare_model

    model_only_update = client.post("/ai-settings", json={
        "provider": "openrouter",
        "api_key": "",
        "model": "openai/gpt-5.6-terra",
    })
    assert model_only_update.status_code == 200
    assert model_only_update.get_json()["image_model"] == flare_model


def test_ai_settings_reject_an_unlisted_image_model(monkeypatch):
    disable_environment_key(monkeypatch)
    client = app_module.app.test_client()

    response = client.post("/ai-settings", json={
        "provider": "openrouter",
        "api_key": "sk-or-v1-test-key-that-is-long-enough",
        "model": "openai/gpt-5.6-terra",
        "image_model": "unknown/image-model",
    })

    assert response.status_code == 400
    assert response.get_json()["error"] == "Choose one of the listed image models."
    assert app_module.AI_SETTINGS_BY_SESSION == {}
