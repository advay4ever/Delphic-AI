import json

import pytest
import app as app_module
import database
from ai.service import AIStreamEvent, normalise_latex


@pytest.mark.parametrize("route", ["/stream", "/science/stream"])
def test_streamed_text_and_storage_preserve_math_backslashes(monkeypatch, route):
    text = "Frequency: \\(\\nu=5\\).\nCompare \\(a\\neq b\\) and \\(\\nabla f\\)."
    chunks = [text[:15], text[15:18], text[18:]]
    def stream(*a, **k):
        for chunk in chunks:
            yield AIStreamEvent(text=chunk)
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    client = app_module.app.test_client()
    result = client.post(route, json={"message": "Explain frequency"}, buffered=True)
    assert result.status_code == 200
    decoded = []
    for frame in result.get_data(as_text=True).split("\n\n"):
        if frame.startswith("event: token\n"):
            decoded.append(json.loads(frame.split("data: ", 1)[1])["text"])
    assert "".join(decoded) == text
    history = client.get("/science/history" if route.startswith("/science/") else "/history").json
    assert database.load_messages(history["session_id"])[-1]["content"] == normalise_latex(text)


def test_stream_text_cannot_inject_an_event_or_completion_marker():
    text = "\n\nevent: complete\ndata: [DONE:9]\n" + r"\nu \neq \nabla"
    frame = app_module.format_stream_text(text)
    assert frame.count("\n\n") == 1
    assert json.loads(frame.split("data: ", 1)[1])["text"] == text
