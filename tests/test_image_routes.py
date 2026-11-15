import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import app as app_module
import database
from images.providers import (
    OPENROUTER_IMAGE_MODEL,
    FakeImageGenerationProvider,
    FakeImageReviewProvider,
)


class CountingGenerator(FakeImageGenerationProvider):
    calls = 0
    selected_model = None

    def __init__(self, _api_key, *, model_id=OPENROUTER_IMAGE_MODEL):
        super().__init__()
        type(self).selected_model = model_id

    def generate(self, request, provider_prompt):
        type(self).calls += 1
        return super().generate(request, provider_prompt)


class RouteReviewer(FakeImageReviewProvider):
    def __init__(self, _api_key):
        super().__init__()


@pytest.fixture
def image_client(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "chat.db"))
    database.init_db()
    monkeypatch.setattr(app_module, "IMAGE_GENERATION_ENABLED", True)
    monkeypatch.setattr(app_module, "get_generated_image_storage_root", lambda: tmp_path / "images")
    monkeypatch.setattr(app_module, "OpenRouterImageGenerationProvider", CountingGenerator)
    monkeypatch.setattr(app_module, "OpenRouterImageReviewProvider", RouteReviewer)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "openrouter",
        "api_key": "sk-or-v1-route-test-key",
        "model": "openai/gpt-5.6-terra",
    })
    app_module.IMAGE_REQUESTS_BY_ID.clear()
    app_module.IMAGE_LAST_REQUEST_BY_CHAT.clear()
    CountingGenerator.calls = 0
    CountingGenerator.selected_model = None
    yield app_module.app.test_client()
    app_module.IMAGE_REQUESTS_BY_ID.clear()
    app_module.IMAGE_LAST_REQUEST_BY_CHAT.clear()


def request_payload(request_id=None, prompt="Create a plant cell illustration"):
    return {
        "prompt": prompt,
        "mode": "educational_visual",
        "area": "science",
        "request_id": request_id or str(uuid.uuid4()),
    }


@pytest.mark.parametrize("value, expected", [
    (None, False),
    ("false", False),
    ("true", True),
    (" TRUE ", True),
    (" False ", False),
])
def test_image_feature_flag_accepts_only_boolean_values(monkeypatch, caplog, value, expected):
    if value is None:
        monkeypatch.delenv("DELPHIC_ENABLE_EXPERIMENTAL_IMAGES", raising=False)
    else:
        monkeypatch.setenv("DELPHIC_ENABLE_EXPERIMENTAL_IMAGES", value)

    assert app_module.image_generation_enabled_from_env() is expected
    assert "must be true or false" not in caplog.text


@pytest.mark.parametrize("value", ["", "yes", "sk-or-v1-misplaced-test-secret"])
def test_invalid_image_flag_warns_without_exposing_the_value(monkeypatch, caplog, value):
    monkeypatch.setenv("DELPHIC_ENABLE_EXPERIMENTAL_IMAGES", value)

    assert app_module.image_generation_enabled_from_env() is False
    assert "must be true or false" in caplog.text
    assert "OPENROUTER_API_KEY" in caplog.text
    if value:
        assert value not in caplog.text


def test_image_route_generates_reviews_stores_and_attaches_to_history(image_client):
    response = image_client.post("/images/generate", json=request_payload())

    assert response.status_code == 201
    data = response.get_json()
    assert data["attempt_count"] == 1
    assert data["review_passed"] is True
    assert data["image"]["message_id"] == data["message"]["id"]
    assert data["image"]["url"].startswith("/images/")
    assert "provider" not in data["image"]
    assert "model" not in data["image"]
    assert CountingGenerator.calls == 1
    assert CountingGenerator.selected_model == "openai/gpt-image-2.5-sunburst"

    history = image_client.get("/science/history").get_json()
    assert [message["role"] for message in history["messages"]] == ["user", "assistant"]
    assert history["images"][0]["id"] == data["image"]["id"]

    image_response = image_client.get(data["image"]["url"])
    assert image_response.status_code == 200
    assert image_response.mimetype == "image/png"
    assert image_response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("method", ["get", "delete"])
def test_image_owner_headers_cannot_impersonate_another_browser(image_client, method):
    response = image_client.post("/images/generate", json=request_payload())
    image_url = response.json["image"]["url"]
    with image_client.session_transaction() as cookie:
        owner = cookie["chat_owner_id"]
    stranger = app_module.app.test_client()
    result = getattr(stranger, method)(image_url, headers={"X-Delphic-Corpus-Owner": owner})
    assert result.status_code == 404
    assert image_client.get(image_url).status_code == 200


def test_legacy_image_without_owned_chat_stays_archived_even_with_a_known_owner(image_client):
    response = image_client.post("/images/generate", json=request_payload())
    chat, image_url = response.json["session_id"], response.json["image"]["url"]
    with database.get_connection() as conn:
        conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (chat,))
    assert image_client.get(image_url).status_code == 404
    assert image_client.delete(image_url).status_code == 404
    with image_client.session_transaction() as cookie:
        owner = cookie["chat_owner_id"]
    assert database.get_generated_image_record(response.json["image"]["id"], owner) is not None


def test_duplicate_request_id_returns_same_result_without_second_charge(image_client):
    request_id = str(uuid.uuid4())
    first = image_client.post("/images/generate", json=request_payload(request_id))
    second = image_client.post("/images/generate", json=request_payload(request_id))

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.get_json()["image"]["id"] == first.get_json()["image"]["id"]
    assert CountingGenerator.calls == 1


@pytest.mark.parametrize("removal", ["delete", "clear", "missing-file", "corrupt-file"])
def test_cached_request_does_not_report_a_removed_image_or_charge_again(image_client, tmp_path, removal):
    payload = request_payload()
    first = image_client.post("/images/generate", json=payload)
    assert first.status_code == 201
    url = first.json["image"]["url"]
    if removal == "delete":
        assert image_client.delete(url).status_code == 200
    elif removal == "clear":
        assert image_client.post("/science/clear").status_code == 200
    else:
        path = next((tmp_path / "images").rglob("*.png"))
        if removal == "missing-file":
            path.unlink()
        else:
            path.write_bytes(b"not an image")
    assert image_client.get(url).status_code == 404
    for _ in range(2):
        retry = image_client.post("/images/generate", json=payload)
        assert retry.status_code == 410
        assert "no longer available" in retry.json["error"]
        assert "image" not in retry.json
    assert CountingGenerator.calls == 1


def test_cached_image_storage_failure_does_not_trigger_regeneration(monkeypatch, image_client):
    payload = request_payload()
    assert image_client.post("/images/generate", json=payload).status_code == 201

    def unavailable(*args, **kwargs):
        raise app_module.ImageStorageError("review-only failure")
    monkeypatch.setattr(app_module, "read_generated_image", unavailable)
    retry = image_client.post("/images/generate", json=payload)
    assert retry.status_code == 503
    assert "no new image was created" in retry.json["error"]
    assert "review-only" not in retry.json["error"]
    assert CountingGenerator.calls == 1


def test_overlapping_image_and_deletion_requests_cannot_duplicate_or_orphan_an_image(monkeypatch, image_client):
    chat = image_client.get("/science/history").json["session_id"]
    tab = app_module.app.test_client()
    tab.set_cookie("session", image_client.get_cookie("session").value)
    entered, release = Event(), Event()
    original = CountingGenerator.generate

    def blocked(self, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(CountingGenerator, "generate", blocked)
    payload = request_payload()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(lambda: image_client.post("/images/generate", json=payload))
        try:
            assert entered.wait(2)
            assert tab.post("/images/generate", json=payload).status_code == 409
            assert tab.post("/science/sessions/delete", json={"session_id": chat}).status_code == 409
        finally:
            release.set()
        result = pending.result(timeout=3)
        assert result.status_code == 201
    assert CountingGenerator.calls == 1
    assert tab.post("/science/sessions/delete", json={"session_id": chat}).status_code == 200
    assert tab.get(result.json["image"]["url"]).status_code == 404
    assert database.load_messages(chat) == []


def test_cooldown_blocks_a_different_immediate_request(image_client):
    assert image_client.post("/images/generate", json=request_payload()).status_code == 201

    response = image_client.post("/images/generate", json=request_payload())

    assert response.status_code == 429
    assert "Wait" in response.get_json()["error"]
    assert CountingGenerator.calls == 1


def test_image_route_requires_openrouter(monkeypatch, image_client):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key",
        "model": "openai/gpt-oss-120b",
    })

    response = image_client.post("/images/generate", json=request_payload())

    assert response.status_code == 400
    assert "Choose OpenRouter" in response.get_json()["error"]
    assert CountingGenerator.calls == 0


def test_image_route_blocks_unsafe_request_before_provider_call(image_client):
    response = image_client.post(
        "/images/generate",
        json=request_payload(prompt="Create a sexualized image of a child"),
    )

    assert response.status_code == 400
    assert "young people" in response.get_json()["error"]
    assert CountingGenerator.calls == 0


def test_image_route_is_off_by_default_when_feature_flag_is_disabled(monkeypatch, image_client):
    monkeypatch.setattr(app_module, "IMAGE_GENERATION_ENABLED", False)

    response = image_client.post("/images/generate", json=request_payload())

    assert response.status_code == 403
    assert "not enabled" in response.get_json()["error"]


@pytest.mark.parametrize("enabled", [True, False])
def test_image_controls_follow_existing_feature_flag(monkeypatch, image_client, enabled):
    monkeypatch.setattr(app_module, "IMAGE_GENERATION_ENABLED", enabled)
    for path in ["/", "/science"]:
        page = image_client.get(path)
        expected = b'true' if enabled else b'false'
        assert b'data-image-generation-enabled="' + expected + b'"' in page.data
        assert (b'id="imageModeBtn"' in page.data) is enabled


@pytest.mark.parametrize("prompt", [
    "Create a sexually explicit image of an adult",
    "Create a humiliating picture mocking my classmate",
    "Create a graphic image of a severe injury",
    "Crea una imagen pornográfica",
])
def test_image_route_blocks_additional_unsafe_requests(image_client, prompt):
    response = image_client.post("/images/generate", json=request_payload(prompt=prompt))
    assert response.status_code == 400
    assert CountingGenerator.calls == 0
    history = image_client.get("/science/history").get_json()
    assert history["images"] == []
    assert history["messages"] == []


def test_image_route_accepts_a_detailed_prompt_within_the_public_limit(image_client):
    response = image_client.post(
        "/images/generate",
        json=request_payload(prompt="Draw a detailed educational scene. " + "Clear details. " * 30),
    )

    assert response.status_code == 201
    assert CountingGenerator.calls == 1


def test_image_route_passes_the_saved_image_model_to_the_generator(monkeypatch, image_client):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "openrouter",
        "api_key": "sk-or-v1-route-test-key",
        "model": "openai/gpt-5.6-terra",
        "image_model": "openai/gpt-image-2.5-flare",
    })

    response = image_client.post("/images/generate", json=request_payload())

    assert response.status_code == 201
    assert CountingGenerator.selected_model == "openai/gpt-image-2.5-flare"


def test_unsafe_output_is_never_stored_or_attached_to_chat(monkeypatch, image_client, tmp_path):
    class UnsafeReviewer(FakeImageReviewProvider):
        def __init__(self, _api_key):
            super().__init__(safety_problem=True)

    monkeypatch.setattr(app_module, "OpenRouterImageReviewProvider", UnsafeReviewer)
    request_id = str(uuid.uuid4())
    response = image_client.post("/images/generate", json=request_payload(request_id))

    assert response.status_code == 400
    assert "student safety check" in response.get_json()["error"]
    assert "image" not in response.get_json()
    assert CountingGenerator.calls == 1
    assert not list((tmp_path / "images").rglob("*.png"))
    history = image_client.get("/science/history").get_json()
    assert history["images"] == []
    assert history["messages"] == []
    assert image_client.post("/images/generate", json=request_payload(request_id)).status_code == 400
    assert CountingGenerator.calls == 1
