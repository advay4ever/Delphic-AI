import pytest

import app as app_module
import database


@pytest.mark.parametrize("prefix", ["", "/science"])
def test_long_history_pages_export_every_message_once_without_expanding_ai_context(prefix):
    client = app_module.app.test_client()
    chat = client.get(prefix + "/history").json["session_id"]
    ids = [database.save_message(chat, "user", f"Entry {i:03}",
                                 sources=[{"title": "Class notes", "excerpt": "Original method"}],
                                 attachments=[{"name": "Original.txt", "kind": "document"}],
                                 diagram={"title": "Original diagram"}) for i in range(125)]
    first = client.get(prefix + "/history").json
    assert len(first["messages"]) == 40
    assert first["total_messages"] == 125
    assert first["has_more"]
    assert first["messages"][0]["id"] == ids[-40]
    assert len(database.load_messages(chat)) == 40
    messages = []
    data = first
    while True:
        messages = data["messages"] + messages
        if not data["has_more"]:
            break
        data = client.post(prefix + "/sessions/messages", json={
            "session_id": chat, "before_id": data["next_before_id"], "snapshot_id": first["snapshot_id"],
        }).json
    assert [m["id"] for m in messages] == ids
    assert messages[0]["attachments"][0]["name"] == "Original.txt"
    assert messages[0]["sources"][0]["excerpt"] == "Original method"
    assert messages[0]["diagram"]["title"] == "Original diagram"


def test_snapshot_cursor_excludes_newer_messages_and_reports_deletion():
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    for i in range(60):
        database.save_message(chat, "user", str(i))
    first = client.get("/history").json
    database.save_message(chat, "user", "Newer question")
    data = client.post("/sessions/messages", json={"session_id": chat, "before_id": first["next_before_id"],
                                                 "snapshot_id": first["snapshot_id"]}).json
    assert data["total_messages"] == 60
    assert len(data["messages"]) == 20
    assert all(m["content"] != "Newer question" for m in data["messages"])
    client.post("/clear")
    data = client.post("/sessions/messages", json={"session_id": chat, "before_id": first["next_before_id"],
                                                 "snapshot_id": first["snapshot_id"]}).json
    assert data["total_messages"] == 0
    assert data["messages"] == []


@pytest.mark.parametrize("cursor", [-1, True, "x", "1.5", [], {}, 2**64])
def test_invalid_history_cursors_fail_safely(cursor):
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    assert client.post("/sessions/messages", json={"session_id": chat, "before_id": cursor}).status_code == 400


def test_graph_restoration_does_not_overwrite_the_latest_equation():
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    database.save_last_equation(chat, "y=x^2")
    assert client.post("/plot", json={"message": "y=x+1", "restore_only": True}).status_code == 200
    assert database.get_last_equation(chat) == "y=x^2"


def test_graph_question_across_a_page_boundary_is_available_for_restoration():
    client = app_module.app.test_client()
    chat = client.get("/history").json["session_id"]
    database.save_message(chat, "user", "Graph y=x^2")
    for _ in range(40):
        database.save_message(chat, "assistant", "Explanation")
    assert client.get("/history").json["graph_context"] == "Graph y=x^2"
