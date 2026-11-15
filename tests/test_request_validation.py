import pytest

import app as app_module
from ai.service import AIResponse, FINISH_REASON_COMPLETE


@pytest.mark.parametrize("path", ["/corpus/notes", "/corpus/notes/preview", "/corpus/notes/text"])
def test_removed_corpus_routes_are_unavailable(path):
    client = app_module.app.test_client()
    assert client.get(path).status_code == 404
    assert client.post(path, json={}).status_code == 404


@pytest.mark.parametrize("path", ["/", "/science"])
def test_tutor_pages_no_longer_offer_corpus_uploads(path):
    response = app_module.app.test_client().get(path)
    assert response.status_code == 200
    assert b"corpus-manager-btn" not in response.data
    assert b"sidebar-study-notes" not in response.data


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/ai-settings"),
        ("post", "/sessions/switch"),
        ("post", "/science/sessions/switch"),
        ("post", "/stream"),
        ("post", "/ask"),
        ("post", "/science/stream"),
        ("post", "/science/ask"),
        ("post", "/plot"),
        ("post", "/local-graph-message"),
    ],
)
def test_json_routes_reject_non_object_payloads(method, path):
    client = app_module.app.test_client()

    response = getattr(client, method)(path, json=["not an object"])

    assert response.status_code == 400
    assert response.get_json() == {"error": "Send a JSON object."}


@pytest.mark.parametrize(
    "path",
    ["/stream", "/ask", "/science/stream", "/science/ask", "/plot", "/local-graph-message"],
)
def test_message_routes_reject_non_text_messages(path):
    client = app_module.app.test_client()

    response = client.post(path, json={"message": ["not text"]})

    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/ask", "/science/ask"])
def test_tutor_routes_accept_one_character_answers(monkeypatch, path):
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
        "source": "test",
    })
    monkeypatch.setattr(
        app_module,
        "get_math_solution",
        lambda *_args, **_kwargs: AIResponse(
            text="Correct.",
            tokens_used=1,
            finish_reason=FINISH_REASON_COMPLETE,
        ),
    )

    client = app_module.app.test_client()
    response = client.post(path, json={"message": "4", "step_by_step_mode": True})

    assert response.status_code == 200
    assert response.get_json()["reply"] == "Correct."
