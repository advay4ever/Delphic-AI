import sqlite3

import app as app_module
import database
from ai.prompt import SCIENCE_TUTOR_SYSTEM_PROMPT
from ai.service import (
    AIResponse,
    FINISH_REASON_COMPLETE,
    FINISH_REASON_ERROR,
    FINISH_REASON_LENGTH,
    MAX_CONTINUATIONS_PER_ANSWER,
)


def _length_limited_message(**overrides):
    message = {
        "id": 17,
        "session_id": "math-chat",
        "role": "assistant",
        "content": "The next step is",
        "finish_reason": FINISH_REASON_LENGTH,
        "continuation_count": 0,
        "can_continue": True,
        "sources": [],
    }
    message.update(overrides)
    return message


def _configure_continuation_route(monkeypatch, message=None):
    monkeypatch.setattr(app_module, "get_message_record", lambda _session_id, _message_id: message or _length_limited_message())
    monkeypatch.setattr(app_module, "load_messages_through", lambda _session_id, _message_id: [
        {"role": "user", "content": "Explain the derivative."},
        {"role": "assistant", "content": "The next step is"},
    ])
    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {
        "provider": "groq",
        "api_key": "gsk-test-key-that-is-long-enough",
        "model": "openai/gpt-oss-120b",
    })
    monkeypatch.setattr(app_module, "get_total_tokens", lambda _session_id: 35)
    monkeypatch.setattr(app_module, "log_tokens", lambda *_args: None)


def test_guided_mode_never_offers_a_continuation():
    assert app_module.continuation_is_available(FINISH_REASON_LENGTH) is True
    assert app_module.continuation_is_available(
        FINISH_REASON_LENGTH,
        guided_mode=True,
    ) is False
    assert app_module.continuation_is_available(FINISH_REASON_COMPLETE) is False


def test_continuation_join_removes_a_clear_repeated_ending():
    original = "Step 1: Differentiate. Step 2: Set the derivative equal to zero."
    continuation = "Step 2: Set the derivative equal to zero. Step 3: Solve for x."

    assert app_module.join_continued_response(original, continuation) == (
        "Step 1: Differentiate. Step 2: Set the derivative equal to zero. "
        "Step 3: Solve for x."
    )


def test_database_migrates_old_messages_and_preserves_continuation_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "old-chat.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            ("old-chat", "assistant", "An older saved answer."),
        )

    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    database.init_db()
    new_id = database.save_message(
        "old-chat",
        "assistant",
        "A partial answer.",
        finish_reason=FINISH_REASON_LENGTH,
        continuation_allowed=True,
        sources=[{
            "title": "Class notes",
            "subject": "math",
            "excerpt": "A short matching excerpt.",
            "score": 0.75,
        }],
    )

    records = database.load_message_records("old-chat")
    assert records[0]["content"] == "An older saved answer."
    assert records[0]["can_continue"] is False
    assert records[1] == {
        "id": new_id,
        "role": "assistant",
        "content": "A partial answer.",
        "finish_reason": FINISH_REASON_LENGTH,
        "continuation_count": 0,
        "can_continue": True,
        "sources": [{
            "title": "Class notes",
            "subject": "math",
            "excerpt": "A short matching excerpt.",
            "score": 0.75,
        }],
        "diagram": None,
        "attachments": [],
    }
    assert database.get_message_record("another-chat", new_id) is None

    assert database.replace_message_with_continuation(
        "old-chat",
        new_id,
        "A partial answer. Finished.",
        FINISH_REASON_COMPLETE,
        False,
        MAX_CONTINUATIONS_PER_ANSWER,
    )
    assert not database.replace_message_with_continuation(
        "old-chat",
        new_id,
        "A second continuation must not be saved.",
        FINISH_REASON_COMPLETE,
        False,
        MAX_CONTINUATIONS_PER_ANSWER,
    )
    updated = database.get_message_record("old-chat", new_id)
    assert updated["content"] == "A partial answer. Finished."
    assert updated["continuation_count"] == 1
    assert updated["can_continue"] is False


def test_math_continuation_uses_saved_text_and_updates_the_same_message(monkeypatch, authorize_chats):
    _configure_continuation_route(monkeypatch)
    captured = {}

    def fake_solution(messages, system_prompt=None, ai_config=None, **_kwargs):
        captured["messages"] = messages
        captured["system_prompt"] = system_prompt
        return AIResponse("differentiate each term.", 14, FINISH_REASON_COMPLETE)

    def fake_replace(*args):
        captured["replace_args"] = args
        return True

    monkeypatch.setattr(app_module, "get_math_solution", fake_solution)
    monkeypatch.setattr(app_module, "replace_message_with_continuation", fake_replace)
    client = app_module.app.test_client()
    authorize_chats(client, "math-chat")
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "math-chat"

    response = client.post("/responses/continue", json={
        "session_id": "math-chat",
        "message_id": 17,
    })

    assert response.status_code == 200
    assert response.get_json()["reply"] == "The next step is differentiate each term."
    assert response.get_json()["finish_reason"] == FINISH_REASON_COMPLETE
    assert response.get_json()["continuation_count"] == 1
    assert response.get_json()["can_continue"] is False
    assert captured["messages"][-2]["content"] == "The next step is"
    assert "Do not repeat" in captured["messages"][-1]["content"]
    assert captured["system_prompt"] is None
    assert captured["replace_args"][1] == 17
    assert captured["replace_args"][2] == "The next step is differentiate each term."


def test_science_continuation_keeps_the_science_system_prompt(monkeypatch, authorize_chats):
    science_message = _length_limited_message(session_id="science:chat")
    _configure_continuation_route(monkeypatch, science_message)
    captured = {}

    def fake_solution(messages, system_prompt=None, ai_config=None, **_kwargs):
        captured["system_prompt"] = system_prompt
        return AIResponse("completed science explanation.", 10, FINISH_REASON_COMPLETE)

    monkeypatch.setattr(app_module, "get_math_solution", fake_solution)
    monkeypatch.setattr(app_module, "replace_message_with_continuation", lambda *_args: True)
    client = app_module.app.test_client()
    authorize_chats(client, "science:chat")
    with client.session_transaction() as flask_session:
        flask_session["science_session_id"] = "science:chat"

    response = client.post("/science/responses/continue", json={
        "session_id": "science:chat",
        "message_id": 17,
    })

    assert response.status_code == 200
    assert captured["system_prompt"] == SCIENCE_TUTOR_SYSTEM_PROMPT


def test_continuation_rejects_a_message_from_another_active_chat(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "get_message_record",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Database should not be queried")),
    )
    client = app_module.app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "active-chat"

    response = client.post("/responses/continue", json={
        "session_id": "different-chat",
        "message_id": 17,
    })

    assert response.status_code == 403
    assert "active chat" in response.get_json()["error"]


def test_failed_continuation_does_not_change_the_saved_message(monkeypatch, authorize_chats):
    _configure_continuation_route(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "get_math_solution",
        lambda *_args, **_kwargs: AIResponse("Private provider failure", 0, FINISH_REASON_ERROR),
    )
    monkeypatch.setattr(
        app_module,
        "replace_message_with_continuation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Failed text must not be saved")),
    )
    client = app_module.app.test_client()
    authorize_chats(client, "math-chat")
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "math-chat"

    response = client.post("/responses/continue", json={
        "session_id": "math-chat",
        "message_id": 17,
    })

    assert response.status_code == 502
    assert response.get_json()["error"] == (
        "The AI provider could not continue this response. Please try again."
    )
    assert "Private provider failure" not in response.get_data(as_text=True)


def test_empty_continuation_does_not_use_the_allowed_attempt(monkeypatch, authorize_chats):
    _configure_continuation_route(monkeypatch)
    monkeypatch.setattr(
        app_module,
        "get_math_solution",
        lambda *_args, **_kwargs: AIResponse("   ", 0, FINISH_REASON_COMPLETE),
    )
    monkeypatch.setattr(
        app_module,
        "replace_message_with_continuation",
        lambda *_args: (_ for _ in ()).throw(AssertionError("Empty text must not be saved")),
    )
    client = app_module.app.test_client()
    authorize_chats(client, "math-chat")
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "math-chat"

    response = client.post("/responses/continue", json={
        "session_id": "math-chat",
        "message_id": 17,
    })

    assert response.status_code == 502
    assert response.get_json()["error"] == (
        "The AI provider could not continue this response. Please try again."
    )


def test_response_cannot_continue_after_its_one_allowed_attempt(monkeypatch, authorize_chats):
    message = _length_limited_message(continuation_count=1)
    _configure_continuation_route(monkeypatch, message)
    client = app_module.app.test_client()
    authorize_chats(client, "math-chat")
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "math-chat"

    response = client.post("/responses/continue", json={
        "session_id": "math-chat",
        "message_id": 17,
    })

    assert response.status_code == 409
    assert "already used" in response.get_json()["error"]
