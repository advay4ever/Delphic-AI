import pytest

import app as app_module
import database
from ai.service import AIResponse, AIStreamEvent


@pytest.mark.parametrize("prefix", ["", "/science"])
@pytest.mark.parametrize("route", ["ask", "stream"])
def test_question_targets_the_tab_chat_not_the_cookie_chat(monkeypatch, prefix, route):
    client = app_module.app.test_client()
    first = client.get(prefix + "/history").json["session_id"]
    database.save_message(first, "assistant", "First chat context")
    second = client.post(prefix + "/sessions/new").json["session_id"]
    database.save_message(second, "assistant", "Other tab context")
    sent = []

    def answer(messages, **kwargs):
        sent.extend(messages)
        return AIResponse("Mock answer", 0, "complete")

    def stream(messages, **kwargs):
        sent.extend(messages)
        yield AIStreamEvent(text="Mock answer")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)

    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    response = client.post(prefix + "/" + route, json={"message": "Explain this lesson"},
                           headers={"X-Delphic-Chat-ID": first}, buffered=True)
    assert response.status_code == 200
    assert "First chat context" in str(sent)
    assert "Other tab context" not in str(sent)
    assert len(database.load_messages(first)) == 3
    assert len(database.load_messages(second)) == 1
    assert client.get(prefix + "/history").json["session_id"] == second
    assert client.get(prefix + "/history", headers={"X-Delphic-Chat-ID": first}).json["session_id"] == first


@pytest.mark.parametrize("path", ["/history", "/science/history", "/plot", "/ask", "/stream", "/clear"])
def test_foreign_or_wrong_tutor_headers_cannot_select_a_chat(path):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    chat = owner.get("/history").json["session_id"]
    database.save_message(chat, "user", "Private")
    if path in {"/history", "/science/history"}:
        response = stranger.get(path, headers={"X-Delphic-Chat-ID": chat})
    else:
        response = stranger.post(path, json={"message": "Explain this"}, headers={"X-Delphic-Chat-ID": chat})
    assert response.status_code == 404
    assert "Private" not in response.get_data(as_text=True)
    assert len(database.load_messages(chat)) == 1


def test_deleted_tab_chat_is_rejected_without_changing_the_other_tab_chat():
    client = app_module.app.test_client()
    first = client.get("/history").json["session_id"]
    second = client.post("/sessions/new").json["session_id"]
    client.post("/sessions/delete", json={"session_id": first})
    assert client.get("/history", headers={"X-Delphic-Chat-ID": first}).status_code == 404
    assert client.get("/history").json["session_id"] == second


@pytest.mark.parametrize("prefix,other", [("", "/science"), ("/science", "")])
def test_even_an_owned_header_must_match_the_requested_tutor(prefix, other):
    client = app_module.app.test_client()
    own = client.get(prefix + "/history").json["session_id"]
    wrong_mode = client.get(other + "/history").json["session_id"]
    assert client.get(prefix + "/history", headers={"X-Delphic-Chat-ID": wrong_mode}).status_code == 404
    assert client.get(prefix + "/history", headers={"X-Delphic-Chat-ID": own}).status_code == 200


def test_graph_finishing_after_deletion_does_not_recreate_session_statistics(monkeypatch):
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    with client.session_transaction() as cookie:
        owner = cookie["chat_owner_id"]

    def build(_message):
        assert database.delete_owned_chat(chat, owner, "math")
        return {"kind": "function_2d", "raw_expression": "y=x", "equation_latex": "x"}

    monkeypatch.setattr(app_module, "build_graph_spec", build)
    assert client.post("/plot", json={"message": "y=x"}, headers={"X-Delphic-Chat-ID": chat}).status_code == 200
    assert database.get_last_equation(chat) is None
