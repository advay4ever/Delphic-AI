from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.error import HTTPError
from urllib.request import urlopen

from flask import Flask
import pytest

import app as app_module
import database
import desktop_launcher
from ai.service import AIResponse, AIStreamEvent


@pytest.mark.parametrize("maximum", [1, 4])
def test_desktop_server_has_bounded_workers_and_recovers_after_a_slow_request(maximum):
    application = Flask(__name__)
    entered, release = Event(), Event()

    @application.get("/slow")
    def slow():
        entered.set()
        assert release.wait(5)
        return "finished"

    @application.get("/health")
    def health():
        return "healthy"

    server, thread = desktop_launcher.start_local_server(application, 0, maximum=maximum)
    base = f"http://127.0.0.1:{server.server_port}"
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: urlopen(base + "/slow", timeout=6).read())
        try:
            assert entered.wait(2)
            assert server.multithread is True
            if maximum == 1:
                with pytest.raises(HTTPError) as error:
                    urlopen(base + "/health", timeout=1)
                assert error.value.code == 503
                assert error.value.headers["Retry-After"] == "1"
                error.value.close()
            else:
                with urlopen(base + "/health", timeout=1) as response:
                    assert response.read() == b"healthy"
            release.set()
            assert future.result(timeout=3) == b"finished"
            with urlopen(base + "/health", timeout=1) as response:
                assert response.read() == b"healthy"
        finally:
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("action", ["/clear", "/sessions/delete", "/sessions/delete-many", "/ask"])
def test_slow_chat_write_blocks_conflicting_actions_but_not_reads(monkeypatch, streaming, action):
    owner = app_module.app.test_client()
    chat = owner.get("/history").json["session_id"]
    other_tab = app_module.app.test_client()
    other_tab.set_cookie("session", owner.get_cookie("session").value)
    entered, release = Event(), Event()
    calls = []

    def answer(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return AIResponse("Mock answer", 3, "complete")

    def stream(*args, **kwargs):
        answer()
        yield AIStreamEvent(text="Mock answer")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=3)

    monkeypatch.setattr(app_module, "detect_and_solve", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(lambda: owner.post("/stream" if streaming else "/ask",
                                               json={"message": "Explain this lesson"}, buffered=True))
        try:
            assert entered.wait(2)
            data = {"message": "Another question", "session_id": chat, "session_ids": [chat]}
            assert other_tab.post(action, json=data).status_code == 409
            assert other_tab.get("/history").status_code == 200
            assert other_tab.get("/library/status?subject=math").status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=3).status_code == 200
    assert len(calls) == 1
    assert other_tab.post("/sessions/delete", json={"session_id": chat}).status_code == 200
    assert database.load_messages(chat) == []
    assert database.get_total_tokens(chat) == 0


def test_releasing_an_old_reservation_cannot_release_a_new_request():
    old, new = object(), object()
    with app_module.CHAT_WRITE_LOCK:
        app_module.CHAT_WRITES_IN_FLIGHT["lease-test"] = new
    try:
        app_module.release_chat_write((("lease-test",), old))
        assert app_module.CHAT_WRITES_IN_FLIGHT["lease-test"] is new
    finally:
        app_module.release_chat_write((("lease-test",), new))


def test_an_unread_stream_close_releases_its_chat_reservation(monkeypatch):
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "get_math_solution_stream", lambda *args, **kwargs: iter([
        AIStreamEvent(text="First words"), AIStreamEvent(done=True, finish_reason="complete", tokens_used=0),
    ]))
    response = client.post("/stream", json={"message": "Explain this"}, buffered=False)
    assert chat in app_module.CHAT_WRITES_IN_FLIGHT
    response.close()
    assert chat not in app_module.CHAT_WRITES_IN_FLIGHT
    assert client.post("/clear").status_code == 200


def test_overlapping_continuations_make_only_one_mock_provider_call(monkeypatch):
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    message = database.save_message(chat, "assistant", "Partial answer", finish_reason="length", continuation_allowed=True)
    tab = app_module.app.test_client()
    tab.set_cookie("session", client.get_cookie("session").value)
    entered, release = Event(), Event()
    calls = []

    def answer(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return AIResponse(" complete", 3, "complete")

    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "get_math_solution", answer)
    payload = {"session_id": chat, "message_id": message}
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(lambda: client.post("/responses/continue", json=payload))
        try:
            assert entered.wait(2)
            assert tab.post("/responses/continue", json=payload).status_code == 409
        finally:
            release.set()
        assert pending.result(timeout=3).status_code == 200
    assert calls == [1]
    assert database.get_total_tokens(chat) == 3
