"""Real-database authorization checks; a known chat UUID is not permission."""

import sqlite3
import uuid
from unittest.mock import Mock

import pytest

import app as app_module
import database
from ai.service import AIResponse, AIStreamEvent


def owned_chat(client, mode):
    prefix = "/science" if mode == "science" else ""
    chat = client.get(prefix + "/history").json["session_id"]
    message_id = database.save_message(
        chat, "assistant", "Private student answer", finish_reason="length",
        continuation_allowed=True, sources=[{"title": "Private notes", "excerpt": "Private class method"}],
        diagram={"title": "Private diagram"},
        attachments=[{"kind": "document", "name": "Private attachment.txt", "text": "Private attachment contents"}],
    )
    database.log_tokens(chat, 19)
    database.save_last_equation(chat, "y=x^2+123")
    return prefix, chat, message_id


@pytest.mark.parametrize("mode", ["math", "science"])
def test_chat_lists_and_history_do_not_leak_other_owners(mode):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    prefix, chat, _ = owned_chat(owner, mode)
    listing = stranger.get(prefix + "/sessions")
    assert listing.status_code == 200
    assert listing.json["sessions"] == []
    assert chat not in listing.get_data(as_text=True)
    assert stranger.get(prefix + "/history").json["messages"] == []
    assert owner.get(prefix + "/sessions").json["sessions"][0]["session_id"] == chat
    own_history = owner.get(prefix + "/history")
    assert own_history.json["messages"][0]["sources"][0]["title"] == "Private notes"
    assert own_history.json["tokens_used"] == 19
    assert own_history.json["messages"][0]["attachments"][0]["name"] == "Private attachment.txt"
    assert own_history.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("mode", ["math", "science"])
@pytest.mark.parametrize("action", ["switch", "messages", "title", "delete", "delete-many"])
def test_known_foreign_chat_id_cannot_authorize_any_session_action(monkeypatch, mode, action):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    prefix, chat, _ = owned_chat(owner, mode)
    generator = Mock(side_effect=AssertionError("Foreign content must not reach a provider"))
    monkeypatch.setattr(app_module, "generate_chat_title", generator)
    with owner.session_transaction() as cookie:
        owner_id = cookie["chat_owner_id"]
    payload = {"session_ids": [chat]} if action == "delete-many" else {"session_id": chat}
    payload["owner_id"] = owner_id
    response = stranger.post(prefix + "/sessions/" + action, json=payload,
                            headers={"X-Delphic-Corpus-Owner": owner_id, "X-Chat-Owner": owner_id})
    assert response.status_code == 404
    assert "Private" not in response.get_data(as_text=True)
    assert database.load_messages(chat)[0]["content"] == "Private student answer"
    assert database.get_total_tokens(chat) == 19
    assert database.chat_session_is_owned(chat, owner_id, mode)
    generator.assert_not_called()


@pytest.mark.parametrize("mode", ["math", "science"])
def test_mixed_owner_bulk_delete_is_rejected_before_any_deletion(mode):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    prefix, private_chat, _ = owned_chat(owner, mode)
    _, own_chat, _ = owned_chat(stranger, mode)
    response = stranger.post(prefix + "/sessions/delete-many", json={"session_ids": [own_chat, private_chat]})
    assert response.status_code == 404
    assert database.load_messages(private_chat)
    assert database.load_messages(own_chat)


@pytest.mark.parametrize("mode", ["math", "science"])
@pytest.mark.parametrize("action", ["history", "clear", "continue"])
def test_foreign_active_chat_cookie_is_not_accepted(monkeypatch, mode, action):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    prefix, private_chat, message_id = owned_chat(owner, mode)
    stranger.get(prefix + "/history")
    key = "science_session_id" if mode == "science" else "session_id"
    with stranger.session_transaction() as cookie:
        cookie[key] = private_chat
    generate = Mock(side_effect=AssertionError("Foreign content must not reach a provider"))
    monkeypatch.setattr(app_module, "get_math_solution", generate)
    if action == "history":
        response = stranger.get(prefix + "/history")
        assert response.json["messages"] == []
        assert response.json["tokens_used"] == 0
    elif action == "clear":
        assert stranger.post(prefix + "/clear").status_code == 200
    else:
        response = stranger.post(prefix + "/responses/continue", json={"session_id": private_chat, "message_id": message_id})
        assert response.status_code == 403
    assert database.load_messages(private_chat)[0]["content"] == "Private student answer"
    assert database.get_last_equation(private_chat) == "y=x^2+123"
    assert database.get_total_tokens(private_chat) == 19
    generate.assert_not_called()


def test_foreign_active_cookie_cannot_restore_private_graph_state():
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    _, chat, _ = owned_chat(owner, "math")
    stranger.get("/history")
    with stranger.session_transaction() as cookie:
        cookie["session_id"] = chat
    response = stranger.post("/plot", json={"message": "zoom in"})
    assert response.status_code == 400
    assert "123" not in response.get_data(as_text=True)
    assert database.get_last_equation(chat) == "y=x^2+123"


@pytest.mark.parametrize("mode", ["math", "science"])
@pytest.mark.parametrize("route", ["ask", "stream"])
def test_foreign_active_cookie_cannot_write_or_forward_private_context(monkeypatch, mode, route):
    owner, stranger = app_module.app.test_client(), app_module.app.test_client()
    prefix, chat, _ = owned_chat(owner, mode)
    stranger.get(prefix + "/history")
    with stranger.session_transaction() as cookie:
        cookie["science_session_id" if mode == "science" else "session_id"] = chat
    sent = []

    def answer(messages, **kwargs):
        sent.extend(messages)
        return AIResponse("Mock lesson.", 0, "complete")

    def stream(messages, **kwargs):
        sent.extend(messages)
        yield AIStreamEvent(text="Mock lesson.")
        yield AIStreamEvent(done=True, finish_reason="complete", tokens_used=0)

    monkeypatch.setattr(app_module, "get_active_ai_config", lambda: {"provider": "groq"})
    monkeypatch.setattr(app_module, "detect_and_solve", lambda *args, **kwargs: None)
    monkeypatch.setattr(app_module, "get_math_solution", answer)
    monkeypatch.setattr(app_module, "get_math_solution_stream", stream)
    response = stranger.post(prefix + "/" + route,
                            json={"message": "Explain this lesson.", "session_id": chat}, buffered=True)
    assert response.status_code == 200
    assert "Private" not in str(sent)
    assert len(database.load_messages(chat)) == 1


@pytest.mark.parametrize("mode", ["math", "science"])
def test_owned_chat_actions_survive_reinitialization_and_cookie_reuse(mode):
    client = app_module.app.test_client()
    prefix, chat, _ = owned_chat(client, mode)
    database.init_db()
    reloaded = app_module.app.test_client()
    reloaded.set_cookie("session", client.get_cookie("session").value)
    assert reloaded.get(prefix + "/history").json["session_id"] == chat
    assert reloaded.post(prefix + "/sessions/switch", json={"session_id": chat}).status_code == 200
    assert reloaded.post(prefix + "/sessions/messages", json={"session_id": chat}).json["tokens_used"] == 19
    assert reloaded.post(prefix + "/sessions/delete", json={"session_id": chat}).status_code == 200
    assert reloaded.post(prefix + "/sessions/switch", json={"session_id": chat}).status_code == 404
    assert database.load_messages(chat) == []
    assert database.get_total_tokens(chat) == 0


def test_legacy_chats_are_preserved_but_never_claimed_by_a_visitor():
    database.save_message("legacy-chat", "user", "Old private question")
    database.save_message("science:legacy-chat", "user", "Old science question")
    for _ in range(2):
        client = app_module.app.test_client()
        for prefix, chat in [("", "legacy-chat"), ("/science", "science:legacy-chat")]:
            assert client.get(prefix + "/sessions").json["sessions"] == []
            assert client.post(prefix + "/sessions/switch", json={"session_id": chat}).status_code == 404
            assert client.post(prefix + "/sessions/delete", json={"session_id": chat}).status_code == 404
    assert database.load_messages("legacy-chat")[0]["content"] == "Old private question"
    with database.get_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM chat_sessions WHERE session_id LIKE '%legacy-chat'").fetchone()[0] == 0


def test_legacy_owner_headers_and_cookies_cannot_choose_a_chat_owner():
    chosen = str(uuid.uuid4())
    client = app_module.app.test_client()
    with client.session_transaction() as cookie:
        cookie["corpus_owner_id"] = chosen
    client.get("/history", headers={"X-Delphic-Corpus-Owner": chosen})
    with client.session_transaction() as cookie:
        assert cookie["chat_owner_id"] != chosen


def test_deletion_tombstone_keeps_late_writes_out_of_owned_history():
    client = app_module.app.test_client()
    _, chat, _ = owned_chat(client, "math")
    assert client.post("/sessions/delete", json={"session_id": chat}).status_code == 200
    database.save_message(chat, "assistant", "Late answer from an earlier request")
    assert client.get("/sessions").json["sessions"] == []
    assert client.post("/sessions/switch", json={"session_id": chat}).status_code == 404


def test_study_library_selection_is_unchanged_by_chat_ownership():
    client = app_module.app.test_client()
    client.get("/")
    with client.session_transaction() as cookie:
        library_owner = cookie["study_library_id"]
    note = database.save_study_note(library_owner, "Class method", "math", "Balance both sides.", False)
    client.post("/sessions/new")
    database.init_db()
    notes = client.get("/library/notes").json["notes"]
    assert notes[0]["id"] == note
    assert notes[0]["enabled"] == 0


def test_full_legacy_metadata_stays_unchanged_and_private_after_upgrade(monkeypatch, tmp_path):
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(tmp_path))
    client = app_module.app.test_client()
    _, chat, message_id = owned_chat(client, "math")
    snapshot = database.load_message_records(chat)
    library_owner = str(uuid.uuid4())
    note_id = database.save_study_note(library_owner, "Original note", "math", "Keep both sides equal", True)
    with database.get_connection() as conn:
        conn.execute("DROP TABLE chat_sessions")
    database.init_db()
    assert database.load_message_records(chat) == snapshot
    assert database.get_message_record(chat, message_id)["can_continue"]
    assert database.get_total_tokens(chat) == 19
    assert database.get_last_equation(chat) == "y=x^2+123"
    assert database.get_study_note(library_owner, note_id)["enabled"] == 1
    assert client.get("/history").json["messages"] == []
    assert client.get("/sessions").json["sessions"] == []


@pytest.mark.parametrize("mode", ["math", "science"])
def test_owner_can_bulk_delete_and_clear_without_affecting_another_browser(mode):
    owner, other = app_module.app.test_client(), app_module.app.test_client()
    prefix, first, _ = owned_chat(owner, mode)
    owner.post(prefix + "/sessions/new")
    _, second, _ = owned_chat(owner, mode)
    _, private, _ = owned_chat(other, mode)
    assert owner.post(prefix + "/sessions/delete-many", json={"session_ids": [first, second]}).status_code == 200
    assert database.load_messages(first) == []
    assert database.load_messages(second) == []
    assert database.load_messages(private)
    _, active, _ = owned_chat(owner, mode)
    assert owner.post(prefix + "/clear").status_code == 200
    assert owner.get(prefix + "/history").json["session_id"] == active
    assert database.load_messages(active) == []
    assert database.load_messages(private)


@pytest.mark.parametrize("route", ["/sessions/switch", "/sessions/messages", "/sessions/delete", "/sessions/title"])
def test_cookie_loss_does_not_allow_claiming_a_previous_chat(route):
    owner = app_module.app.test_client()
    _, chat, _ = owned_chat(owner, "math")
    owner.delete_cookie("session")
    assert owner.post(route, json={"session_id": chat}).status_code == 404
    assert database.load_messages(chat)


def test_privacy_upgrade_backs_up_legacy_database_and_images_before_schema_change(monkeypatch, tmp_path):
    path = tmp_path / "old.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(tmp_path))
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, created_at DATETIME)")
        conn.execute("INSERT INTO messages VALUES (1, 'old', 'user', 'Keep me', CURRENT_TIMESTAMP)")
    image = tmp_path / "generated_images" / "legacy-owner" / "saved.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"unchanged legacy image")
    database.init_db()
    backup = list((tmp_path / "ownership-backups").iterdir())
    assert len(backup) == 1
    with sqlite3.connect(backup[0] / "chat_history.db") as conn:
        assert conn.execute("SELECT content FROM messages").fetchone()[0] == "Keep me"
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'chat_sessions'").fetchone() is None
    assert (backup[0] / "generated_images" / "legacy-owner" / "saved.png").read_bytes() == image.read_bytes()
    assert database.load_messages("old")[0]["content"] == "Keep me"
    assert database.list_all_sessions(owner_id=str(uuid.uuid4()), mode="math") == []
    database.init_db()
    assert len(list((tmp_path / "ownership-backups").iterdir())) == 1


def test_failed_legacy_image_backup_stops_upgrade_without_changing_the_database(monkeypatch, tmp_path):
    path = tmp_path / "old.db"
    monkeypatch.setattr(database, "DB_PATH", str(path))
    monkeypatch.setenv("DELPHIC_DATA_DIR", str(tmp_path))
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE messages (content TEXT)")
        conn.execute("INSERT INTO messages VALUES ('Preserved')")
    (tmp_path / "generated_images").mkdir()
    monkeypatch.setattr(database.shutil, "copytree", Mock(side_effect=OSError("test backup failure")))
    with pytest.raises(RuntimeError, match="legacy backup"):
        database.init_db()
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT content FROM messages").fetchone()[0] == "Preserved"
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'chat_sessions'").fetchone() is None
