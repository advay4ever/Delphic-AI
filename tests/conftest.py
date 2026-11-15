import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

import database

# app.py initializes storage during test collection, before per-test fixtures run.
_startup_data = TemporaryDirectory(prefix="delphic-pytest-startup-")
database.DB_PATH = str(Path(_startup_data.name) / "chat_history.db")


@pytest.fixture
def authorize_chats():
    """Give a test browser explicit ownership; never bypass authorization checks."""
    def assign(client, *session_ids):
        with client.session_transaction() as cookie:
            owner = cookie.setdefault("chat_owner_id", str(uuid.uuid4()))
        with database.get_connection() as conn:
            for session_id in session_ids:
                mode = "science" if session_id.startswith("science:") else "math"
                conn.execute("INSERT INTO chat_sessions (session_id, owner_id, mode) VALUES (?, ?, ?)",
                             (session_id, owner, mode))
        return client
    return assign


@pytest.fixture(autouse=True)
def isolate_test_database(monkeypatch, tmp_path):
    """Keep every Python test away from the developer's real chat history."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "chat_history.db"))
    database.init_db()
