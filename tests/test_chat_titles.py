import json
from unittest.mock import Mock

import pytest

import ai.chat_titles as titles
import app as app_module
import database
from ai.service import AIResponse, FINISH_REASON_COMPLETE, FINISH_REASON_ERROR


def seed_chat(session_id="chat"):
    first_id = database.save_message(session_id, "user", "Why do points in a scatter plot go up together?")
    database.save_message(session_id, "assistant", "That is positive correlation.", finish_reason="complete")
    return first_id


@pytest.mark.parametrize("session_id,path", [
    ("chat", "/sessions"), ("science:chat", "/science/sessions"),
])
def test_summary_is_saved_once_and_survives_later_questions(monkeypatch, session_id, path, authorize_chats):
    seed_chat(session_id)
    mock_title = Mock(return_value=AIResponse("Understanding Positive Correlation", 17, "complete"))
    monkeypatch.setattr(app_module, "generate_chat_title", mock_title)
    config = {"provider": "groq", "api_key": "test-only"}
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: config)
    client = app_module.app.test_client()
    authorize_chats(client, session_id)

    response = client.post(path + "/title", json={"session_id": session_id})
    assert response.status_code == 200
    assert response.json["title"] == "Understanding Positive Correlation"
    assert response.json["tokens_used"] == 17
    assert response.json["title_generated"] is True
    assert mock_title.call_args.args[1] == config

    database.save_message(session_id, "user", "And what if they go down?")
    database.init_db()
    other_client = app_module.app.test_client()
    other_client.set_cookie("session", client.get_cookie("session").value)
    listed = other_client.get(path).json["sessions"]
    assert listed[0]["preview"] == "Understanding Positive Correlation"
    other_client.post(path + "/title", json={"session_id": session_id})
    assert mock_title.call_count == 1
    assert database.get_total_tokens(session_id) == 17


def test_first_exchange_uses_message_order_instead_of_alphabetical_order():
    first_id = seed_chat()
    for _ in range(45):
        database.save_message("chat", "user", "A later follow-up")
    context = database.get_session_title_context("chat")
    assert context["first_message_id"] == first_id
    assert context["messages"][0]["content"].startswith("Why do points")
    assert context["messages"][1]["content"] == "That is positive correlation."
    assert database.list_all_sessions()[0]["preview"].startswith("Why do points")


@pytest.mark.parametrize("path,session_id,status", [
    ("/sessions/title", "science:chat", 400),
    ("/science/sessions/title", "chat", 400),
    ("/sessions/title", "missing-chat", 404),
])
def test_title_endpoint_validates_chat_and_tutor(monkeypatch, path, session_id, status):
    seed_chat("chat")
    seed_chat("science:chat")
    generate = Mock()
    monkeypatch.setattr(app_module, "generate_chat_title", generate)
    response = app_module.app.test_client().post(path, json={"session_id": session_id})
    assert response.status_code == status
    generate.assert_not_called()


def test_generation_waits_for_an_answer_and_an_api_key(monkeypatch, authorize_chats):
    generate = Mock()
    monkeypatch.setattr(app_module, "generate_chat_title", generate)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    database.save_message("chat", "user", "Explain scatter plots")
    client = app_module.app.test_client()
    authorize_chats(client, "chat")
    assert not client.post("/sessions/title", json={"session_id": "chat"}).json["title_generated"]
    database.save_message("chat", "assistant", "Provider unavailable", finish_reason="error")
    assert not client.post("/sessions/title", json={"session_id": "chat"}).json["title_generated"]
    database.save_message("chat", "assistant", "Scatter plots show pairs of values.")
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: None)
    assert not client.post("/sessions/title", json={"session_id": "chat"}).json["title_generated"]
    generate.assert_not_called()


def test_failed_generation_keeps_fallback_and_can_retry(monkeypatch, authorize_chats):
    seed_chat()
    generate = Mock(side_effect=[
        AIResponse("", 0, FINISH_REASON_ERROR),
        AIResponse("Understanding Scatter Plots", 12, FINISH_REASON_COMPLETE),
    ])
    monkeypatch.setattr(app_module, "generate_chat_title", generate)
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    client = app_module.app.test_client()
    authorize_chats(client, "chat")
    assert not client.post("/sessions/title", json={"session_id": "chat"}).json["title_generated"]
    assert database.list_all_sessions()[0]["preview"].startswith("Why do points")
    assert client.post("/sessions/title", json={"session_id": "chat"}).json["title_generated"]
    assert len(database.load_messages("chat")) == 2


@pytest.mark.parametrize("reuse_session", [False, True])
def test_late_title_does_not_restore_deleted_or_cleared_chat(monkeypatch, reuse_session, authorize_chats):
    seed_chat()
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})

    def delayed_title(*_args):
        database.clear_messages("chat")
        if reuse_session:
            database.save_message("chat", "user", "Explain triangles")
        return AIResponse("Understanding Scatter Plots", 12, "complete")

    monkeypatch.setattr(app_module, "generate_chat_title", delayed_title)
    client = authorize_chats(app_module.app.test_client(), "chat")
    response = client.post("/sessions/title", json={"session_id": "chat"})
    assert not response.json["title_generated"]
    assert database.get_total_tokens("chat") == 0
    if not reuse_session:
        assert database.list_all_sessions() == []


def test_overlapping_requests_do_not_generate_two_titles(monkeypatch, authorize_chats):
    seed_chat()
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    client = authorize_chats(app_module.app.test_client(), "chat")

    def generate(*_args):
        other_tab = app_module.app.test_client()
        other_tab.set_cookie("session", client.get_cookie("session").value)
        nested = other_tab.post("/sessions/title", json={"session_id": "chat"})
        assert nested.status_code == 200
        assert not nested.json["title_generated"]
        return AIResponse("Understanding Scatter Plots", 12, "complete")

    mock_title = Mock(side_effect=generate)
    monkeypatch.setattr(app_module, "generate_chat_title", mock_title)
    response = client.post("/sessions/title", json={"session_id": "chat"})
    assert response.json["title_generated"]
    assert mock_title.call_count == 1


def test_title_request_uses_bounded_text_and_selected_provider(monkeypatch):
    generate = Mock(return_value=AIResponse('"Understanding Scatter Plots"', 15, "complete"))
    monkeypatch.setattr(titles, "get_math_solution", generate)
    config = {"provider": "anthropic", "api_key": "test-only"}
    response = titles.generate_chat_title([
        {"role": "user", "content": "Explain scatter plots", "_attachments": [{"data_url": "private bytes"}]},
        {"role": "assistant", "content": "a" * 5000},
    ], config)
    assert response.text == "Understanding Scatter Plots"
    sent = json.loads(generate.call_args.args[0][0]["content"])
    assert set(sent[0]) == {"role", "content"}
    assert len(sent[1]["content"]) == 3000
    assert generate.call_args.kwargs["ai_config"] == config
    assert generate.call_args.kwargs["system_prompt"] == titles.CHAT_TITLE_PROMPT


@pytest.mark.parametrize("text,reason", [
    ("", "complete"), ("a" * 51, "complete"), ("Title: Scatter Plots", "complete"),
    ("Scatter Plots\nHere is why", "complete"), ("<b>Scatter Plots</b>", "complete"),
    ("# Scatter Plots", "complete"), ("Provider unavailable", "error"),
    ("A partial title", "length"),
])
def test_invalid_provider_output_is_not_saved_as_a_title(monkeypatch, text, reason):
    monkeypatch.setattr(titles, "get_math_solution", lambda *_args, **_kwargs: AIResponse(text, 5, reason))
    assert titles.generate_chat_title([], {}).text == ""


def test_title_column_migrates_existing_database_without_losing_chats():
    seed_chat()
    with database.get_connection() as conn:
        conn.execute("ALTER TABLE session_stats DROP COLUMN title")
    database.init_db()
    database.init_db()
    assert database.get_session_title_context("chat")["title"] == ""
    assert len(database.load_messages("chat")) == 2
