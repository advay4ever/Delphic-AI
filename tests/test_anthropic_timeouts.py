import json
from types import SimpleNamespace

import httpx
import pytest
import app as app_module
import ai.service as service
import database


CONFIG = {"provider": "anthropic", "api_key": "anthropic-test-only-key", "model": "claude-haiku-4-5-20251001"}


def mock_transport(monkeypatch, behavior, captured):
    real_client = httpx.Client
    class Body(httpx.SyncByteStream):
        def __iter__(self):
            yield ("data: " + json.dumps({"type": "content_block_delta", "delta": {"text": "A partial explanation. "}}) + "\n\n").encode()
            if behavior == "read":
                raise httpx.ReadTimeout("Private timeout detail")
            yield b': ping\n\n'
            yield b'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}\n\n'
        def close(self):
            captured["closed"] = True
    def handler(request):
        captured["timeouts"] = request.extensions["timeout"]
        if behavior == "connect":
            raise httpx.ConnectTimeout("Private connection detail")
        return httpx.Response(200, stream=Body())
    monkeypatch.setattr(service.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))


@pytest.mark.parametrize("behavior", ["healthy", "connect", "read", "window"])
def test_anthropic_stream_has_finite_limits_and_closes_on_failure(monkeypatch, behavior):
    captured = {}
    mock_transport(monkeypatch, behavior, captured)
    if behavior == "window":
        ticks = iter([0, 1, 181])
        monkeypatch.setattr(service.time, "monotonic", lambda: next(ticks))
    events = list(service.get_math_solution_stream([], ai_config=CONFIG))
    assert all(value is not None and 0 < value <= 60 for value in captured["timeouts"].values())
    if behavior == "healthy":
        assert events[-1].finish_reason == "complete"
    else:
        assert events[-1].finish_reason == "error"
        assert "Private" not in events[-1].text
    if behavior != "connect":
        assert events[0].text == "A partial explanation. "
        assert captured["closed"]


@pytest.mark.parametrize("prefix", ["", "/science"])
def test_stalled_provider_preserves_partial_text_and_releases_the_chat(monkeypatch, prefix):
    captured = {}
    mock_transport(monkeypatch, "read", captured)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: CONFIG)
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)
    client = app_module.app.test_client()
    chat = client.get(prefix + "/history").json["session_id"]
    response = client.post(prefix + "/stream", json={"message": "Explain this lesson"}, buffered=True)
    assert response.status_code == 200
    assert '"finish_reason": "error"' in response.get_data(as_text=True)
    saved = database.load_message_records(chat)[-1]
    assert saved["content"].startswith("A partial explanation.")
    assert saved["finish_reason"] == "error"
    assert chat not in app_module.CHAT_WRITES_IN_FLIGHT
    assert captured["closed"]
    assert client.post(prefix + "/clear").status_code == 200


def test_slow_stream_without_line_endings_cannot_bypass_the_window(monkeypatch):
    ticks = iter([1, 181])
    monkeypatch.setattr(service.time, "monotonic", lambda: next(ticks))
    response = SimpleNamespace(iter_text=lambda: iter(["data: ", "more data without a newline"]))
    with pytest.raises(httpx.ReadTimeout):
        list(service._anthropic_stream_lines(response, 0))


def test_oversized_unterminated_event_is_rejected():
    response = SimpleNamespace(iter_text=lambda: iter(["x" * 128_001]))
    with pytest.raises(ValueError):
        list(service._anthropic_stream_lines(response, service.time.monotonic()))
