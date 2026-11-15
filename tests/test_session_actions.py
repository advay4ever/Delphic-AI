import app as app_module


def test_math_session_download_returns_selected_messages(monkeypatch, authorize_chats):
    client = app_module.app.test_client()
    authorize_chats(client, "math-chat")
    monkeypatch.setattr(
        app_module,
        "load_message_page",
        lambda session_id, **kwargs: {"messages": [{"role": "user", "content": f"Question from {session_id}"}]},
    )
    monkeypatch.setattr(app_module, "get_total_tokens", lambda _session_id: 12)

    response = client.post("/sessions/messages", json={"session_id": "math-chat"})

    assert response.status_code == 200
    assert response.get_json() == {
        "session_id": "math-chat",
        "messages": [{"role": "user", "content": "Question from math-chat"}],
        "images": [],
        "tokens_used": 12,
    }


def test_session_actions_reject_a_chat_from_the_other_tutor():
    client = app_module.app.test_client()

    response = client.post("/sessions/messages", json={"session_id": "science:cell-chat"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "That chat belongs to a different tutor."


def test_deleting_a_past_chat_keeps_the_active_math_chat(monkeypatch, authorize_chats):
    client = app_module.app.test_client()
    authorize_chats(client, "active-chat", "past-chat")
    deleted_ids = []
    monkeypatch.setattr(app_module, "delete_owned_chat", lambda chat, owner, mode: deleted_ids.append(chat))
    deleted_image_sessions = []
    monkeypatch.setattr(
        app_module,
        "delete_generated_images_for_chat",
        lambda session_id: deleted_image_sessions.append(session_id),
    )
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "active-chat"

    response = client.post("/sessions/delete", json={"session_id": "past-chat"})

    assert response.status_code == 200
    assert response.get_json() == {
        "deleted_session_id": "past-chat",
        "current_session_id": "active-chat",
    }
    assert deleted_ids == ["past-chat"]
    assert deleted_image_sessions == ["past-chat"]


def test_deleting_the_active_science_chat_starts_a_new_science_chat(monkeypatch, authorize_chats):
    client = app_module.app.test_client()
    authorize_chats(client, "science:active-chat")
    deleted_ids = []
    monkeypatch.setattr(app_module, "delete_owned_chat", lambda chat, owner, mode: deleted_ids.append(chat))
    deleted_image_sessions = []
    monkeypatch.setattr(
        app_module,
        "delete_generated_images_for_chat",
        lambda session_id: deleted_image_sessions.append(session_id),
    )
    with client.session_transaction() as flask_session:
        flask_session["science_session_id"] = "science:active-chat"

    response = client.post("/science/sessions/delete", json={"session_id": "science:active-chat"})

    assert response.status_code == 200
    data = response.get_json()
    assert data["deleted_session_id"] == "science:active-chat"
    assert data["current_session_id"].startswith("science:")
    assert data["current_session_id"] != "science:active-chat"
    assert deleted_ids == ["science:active-chat"]
    assert deleted_image_sessions == ["science:active-chat"]


def test_deleting_multiple_math_chats_uses_one_request(monkeypatch, authorize_chats):
    client = app_module.app.test_client()
    authorize_chats(client, "active-chat", "past-one", "past-two")
    deleted_ids = []
    deleted_image_sessions = []
    monkeypatch.setattr(app_module, "delete_owned_chat", lambda chat, owner, mode: deleted_ids.append(chat))
    monkeypatch.setattr(
        app_module,
        "delete_generated_images_for_chat",
        deleted_image_sessions.append,
    )
    with client.session_transaction() as flask_session:
        flask_session["session_id"] = "active-chat"

    response = client.post(
        "/sessions/delete-many",
        json={"session_ids": ["past-one", "past-two", "past-one"]},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "deleted_session_ids": ["past-one", "past-two"],
        "current_session_id": "active-chat",
    }
    assert deleted_ids == ["past-one", "past-two"]
    assert deleted_image_sessions == ["past-one", "past-two"]


def test_bulk_delete_rejects_mixed_tutor_chats_before_deleting(monkeypatch):
    client = app_module.app.test_client()
    deleted_ids = []
    monkeypatch.setattr(app_module, "delete_owned_chat", lambda chat, owner, mode: deleted_ids.append(chat))

    response = client.post(
        "/sessions/delete-many",
        json={"session_ids": ["math-chat", "science:cell-chat"]},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "One selected chat belongs to a different tutor."
    assert deleted_ids == []


def test_bulk_delete_replaces_an_active_science_chat_once(monkeypatch, authorize_chats):
    client = app_module.app.test_client()
    authorize_chats(client, "science:active-chat", "science:past-chat")
    deleted_ids = []
    monkeypatch.setattr(app_module, "delete_owned_chat", lambda chat, owner, mode: deleted_ids.append(chat))
    monkeypatch.setattr(app_module, "delete_generated_images_for_chat", lambda _session_id: 0)
    with client.session_transaction() as flask_session:
        flask_session["science_session_id"] = "science:active-chat"

    response = client.post(
        "/science/sessions/delete-many",
        json={"session_ids": ["science:active-chat", "science:past-chat"]},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["deleted_session_ids"] == ["science:active-chat", "science:past-chat"]
    assert data["current_session_id"].startswith("science:")
    assert data["current_session_id"] not in data["deleted_session_ids"]
    assert deleted_ids == ["science:active-chat", "science:past-chat"]
