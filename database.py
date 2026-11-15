"""
Math AI Agent - Database (SQLite conversation persistence)

Stores chat messages so they survive browser refreshes and server restarts.
"""

import sqlite3
import os
import re
import json
import shutil
import uuid
from ai.attachments import public_attachments
from pathlib import Path


def _database_path() -> str:
    data_dir = os.getenv("DELPHIC_DATA_DIR")
    if data_dir:
        path = Path(data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return str(path / "chat_history.db")
    return os.path.join(os.path.dirname(__file__), "chat_history.db")


DB_PATH = _database_path()


def get_connection():
    """Open a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    if os.name != "nt":
        try:
            Path(DB_PATH).chmod(0o600)
        except OSError:
            pass
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn


def init_db():
    """Create all tables if they don't exist yet."""
    with get_connection() as conn:
        _backup_before_chat_ownership(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK (mode IN ('math', 'science')),
                deleted INTEGER NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_owner ON chat_sessions(owner_id, mode, deleted)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                finish_reason TEXT,
                continuation_count INTEGER NOT NULL DEFAULT 0,
                continuation_allowed INTEGER NOT NULL DEFAULT 0,
                source_metadata TEXT NOT NULL DEFAULT '[]',
                diagram_spec TEXT NOT NULL DEFAULT 'null',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id, id)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                tokens     INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS study_notes (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL,
                text TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                revision INTEGER NOT NULL DEFAULT 1,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_study_notes_owner ON study_notes(owner_id)")
        note_columns = {row["name"] for row in conn.execute("PRAGMA table_info(study_notes)")}
        if "revision" not in note_columns:
            conn.execute("ALTER TABLE study_notes ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
        if "updated_at" not in note_columns:
            conn.execute("ALTER TABLE study_notes ADD COLUMN updated_at DATETIME")
            conn.execute("UPDATE study_notes SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                session_id     TEXT PRIMARY KEY,
                question_count INTEGER DEFAULT 0,
                topics_seen    TEXT DEFAULT '',
                last_equation  TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generated_images (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message_id INTEGER,
                prompt TEXT NOT NULL,
                image_request_json TEXT NOT NULL,
                review_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                local_filename TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_generated_images_owner_session
            ON generated_images (owner_id, session_id, created_at)
        """)
        # Migrate: add last_equation column if it doesn't exist yet (for existing DBs)
        try:
            conn.execute("ALTER TABLE session_stats ADD COLUMN last_equation TEXT DEFAULT ''")
        except Exception:
            pass  # Column already exists — that's fine
        stats_columns = {row["name"] for row in conn.execute("PRAGMA table_info(session_stats)")}
        if "title" not in stats_columns:
            conn.execute("ALTER TABLE session_stats ADD COLUMN title TEXT NOT NULL DEFAULT ''")
        message_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "finish_reason" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN finish_reason TEXT")
        if "continuation_count" not in message_columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN continuation_count INTEGER NOT NULL DEFAULT 0"
            )
        if "continuation_allowed" not in message_columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN continuation_allowed INTEGER NOT NULL DEFAULT 0"
            )
        if "source_metadata" not in message_columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN source_metadata TEXT NOT NULL DEFAULT '[]'"
            )
        if "diagram_spec" not in message_columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN diagram_spec TEXT NOT NULL DEFAULT 'null'"
            )
        if "attachment_context" not in message_columns:
            conn.execute("ALTER TABLE messages ADD COLUMN attachment_context TEXT NOT NULL DEFAULT '[]'")
        conn.commit()


def _backup_before_chat_ownership(conn):
    """Leave old chats unassigned; back up their database and images before DDL."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "chat_sessions" in tables:
        return
    legacy_tables = tables & {"messages", "session_stats", "token_usage", "generated_images", "study_notes"}
    if not any(conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in legacy_tables):
        return
    data_root = Path(DB_PATH).parent
    if not os.getenv("DELPHIC_DATA_DIR"):
        data_root /= "instance"
    backup = data_root / "ownership-backups" / uuid.uuid4().hex
    try:
        backup.mkdir(parents=True, mode=0o700)
        backup.parent.chmod(0o700)
        with sqlite3.connect(backup / "chat_history.db") as destination:
            conn.backup(destination)
        (backup / "chat_history.db").chmod(0o600)
        images = data_root / "generated_images"
        if images.is_symlink():
            raise OSError("Legacy image root must be a local directory")
        if images.exists():
            shutil.copytree(images, backup / "generated_images", symlinks=True)
    except (OSError, sqlite3.Error) as error:
        raise RuntimeError("Chat privacy upgrade stopped: the legacy backup could not be completed.") from error


def create_chat_session(owner_id: str, mode: str) -> str:
    if mode not in {"math", "science"}:
        raise ValueError("Unknown tutor mode")
    session_id = ("science:" if mode == "science" else "") + str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute("INSERT INTO chat_sessions (session_id, owner_id, mode) VALUES (?, ?, ?)",
                     (session_id, owner_id, mode))
    return session_id


def chat_session_is_owned(session_id: str, owner_id: str, mode: str) -> bool:
    with get_connection() as conn:
        return conn.execute(
            "SELECT 1 FROM chat_sessions WHERE session_id = ? AND owner_id = ? AND mode = ? AND deleted = 0",
            (session_id, owner_id, mode),
        ).fetchone() is not None


def delete_owned_chat(session_id: str, owner_id: str, mode: str) -> bool:
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        updated = conn.execute(
            "UPDATE chat_sessions SET deleted = 1 WHERE session_id = ? AND owner_id = ? AND mode = ? AND deleted = 0",
            (session_id, owner_id, mode),
        )
        if updated.rowcount != 1:
            return False
        for table in ("messages", "token_usage", "session_stats"):
            conn.execute(f"DELETE FROM {table} WHERE session_id = ?", (session_id,))
    return True


def save_message(
    session_id: str,
    role: str,
    content: str,
    finish_reason: str | None = None,
    continuation_allowed: bool = False,
    sources: list[dict] | None = None,
    diagram: dict | None = None,
    attachments: list[dict] | None = None,
) -> int:
    """Save one message and return its stable database ID."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO messages (
                session_id, role, content, finish_reason, continuation_allowed,
                source_metadata, diagram_spec, attachment_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                finish_reason,
                int(continuation_allowed),
                json.dumps(sources or [], ensure_ascii=True),
                json.dumps(diagram, ensure_ascii=True),
                json.dumps(attachments or [], ensure_ascii=True),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_study_notes(owner_id: str, subject: str | None = None) -> list[dict]:
    with get_connection() as conn:
        if subject:
            rows = conn.execute(
                "SELECT * FROM study_notes WHERE owner_id = ? AND enabled = 1 AND subject IN (?, 'both') ORDER BY created_at, id",
                (owner_id, subject),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM study_notes WHERE owner_id = ? ORDER BY created_at DESC, id",
                (owner_id,),
            ).fetchall()
    return [dict(row) for row in rows]


def get_study_note(owner_id: str, note_id: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM study_notes WHERE owner_id = ? AND id = ?",
                           (owner_id, note_id)).fetchone()
    return dict(row) if row else None


def save_study_note(owner_id: str, title: str, subject: str, text: str, enabled: bool) -> str:
    import uuid
    from ai.study_library import MAX_NOTES, StudyLibraryError
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) FROM study_notes WHERE owner_id = ?", (owner_id,)).fetchone()[0]
        if count >= MAX_NOTES:
            raise StudyLibraryError("Your Study Library is full. Delete a note before adding another.")
        note_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO study_notes (id, owner_id, title, subject, text, enabled, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, STRFTIME('%Y-%m-%d %H:%M:%f', 'now'))",
            (note_id, owner_id, title, subject, text, int(enabled)),
        )
    return note_id


def count_enabled_study_notes(owner_id: str, subject: str) -> int:
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM study_notes WHERE owner_id = ? AND enabled = 1 AND subject IN (?, 'both')",
            (owner_id, subject),
        ).fetchone()[0]


def change_study_note(owner_id: str, note_id: str, enabled: bool | None = None, title: str | None = None) -> bool:
    with get_connection() as conn:
        if enabled is None and title is None:
            cursor = conn.execute("DELETE FROM study_notes WHERE owner_id = ? AND id = ?", (owner_id, note_id))
        else:
            fields, values = [], []
            if enabled is not None:
                fields.append("enabled = ?")
                values.append(int(enabled))
            if title is not None:
                fields.append("title = ?")
                values.append(title)
                fields.append("updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now')")
            cursor = conn.execute(
                "UPDATE study_notes SET " + ", ".join(fields) + ", revision = revision + 1 WHERE owner_id = ? AND id = ?",
                (*values, owner_id, note_id),
            )
    return cursor.rowcount == 1


def edit_study_note(owner_id: str, note_id: str, title: str, subject: str,
                    text: str, revision: int) -> dict | None:
    from ai.study_library import StudyLibraryConflict
    with get_connection() as conn:
        # Serialize the version check and update, including competing rename/selection writes.
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT * FROM study_notes WHERE owner_id = ? AND id = ?", (owner_id, note_id),
        ).fetchone()
        if current is None:
            return None
        if current["revision"] != revision:
            raise StudyLibraryConflict(
                "This note changed in another tab. Your draft is still here. "
                "Load the latest saved note before editing again."
            )
        conn.execute(
            "UPDATE study_notes SET title = ?, subject = ?, text = ?, revision = revision + 1, "
            "updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now') "
            "WHERE owner_id = ? AND id = ? AND revision = ?",
            (title, subject, text, owner_id, note_id, revision),
        )
        return dict(conn.execute(
            "SELECT * FROM study_notes WHERE owner_id = ? AND id = ?", (owner_id, note_id),
        ).fetchone())


def log_tokens(session_id: str, tokens: int):
    """Log token usage for a session."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO token_usage (session_id, tokens) VALUES (?, ?)",
            (session_id, tokens),
        )
        conn.commit()


def get_total_tokens(session_id: str) -> int:
    """Get the total tokens used in this session."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens), 0) FROM token_usage WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return row[0] if row else 0


def load_messages(session_id: str, limit: int = 40) -> list[dict]:
    """Load the most recent messages for a session."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, attachment_context FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    # Reverse so oldest message is first
    return [_provider_message(row) for row in reversed(rows)]


def _attachment_context(raw_value: str | None) -> list[dict]:
    try:
        value = json.loads(raw_value or "[]")
    except (TypeError, ValueError):
        return []
    return [item for item in value if isinstance(item, dict)][:3] if isinstance(value, list) else []


def _provider_message(row) -> dict:
    message = {"role": row["role"], "content": row["content"]}
    items = _attachment_context(row["attachment_context"])
    if items:
        message["_attachments"] = items
    return message


def load_message_records(session_id: str, limit: int = 40, *, before_id=None, snapshot_id=None) -> list[dict]:
    """Load messages with the metadata needed to rebuild the chat screen."""
    filters = ""
    parameters = [session_id]
    if before_id is not None:
        filters += " AND id < ?"
        parameters.append(before_id)
    if snapshot_id is not None:
        filters += " AND id <= ?"
        parameters.append(snapshot_id)
    parameters.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, role, content, finish_reason,
                   continuation_count, continuation_allowed, source_metadata, diagram_spec, attachment_context
            FROM messages
            WHERE session_id = ? """ + filters + """
            ORDER BY id DESC
            LIMIT ?
            """,
            parameters,
        ).fetchall()
    return [
        {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "finish_reason": row["finish_reason"],
            "continuation_count": row["continuation_count"],
            "can_continue": bool(row["continuation_allowed"]),
            "sources": _load_source_metadata(row["source_metadata"]),
            "diagram": _load_diagram_spec(row["diagram_spec"]),
            "attachments": public_attachments(_attachment_context(row["attachment_context"])),
        }
        for row in reversed(rows)
    ]


def load_message_page(session_id: str, *, before_id=None, snapshot_id=None, limit=40) -> dict:
    """Page screen/export history separately from the AI's bounded context."""
    if not 1 <= limit <= 100:
        raise ValueError("Choose a page size between 1 and 100.")
    for value in (before_id, snapshot_id):
        if value is not None and (type(value) is not int or not 0 <= value <= 2**63 - 1):
            raise ValueError("Use a valid history cursor.")
    with get_connection() as conn:
        if snapshot_id is None:
            snapshot_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages WHERE session_id = ?",
                                       (session_id,)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = ? AND id <= ?",
                             (session_id, snapshot_id)).fetchone()[0]
    records = load_message_records(session_id, limit + 1, before_id=before_id, snapshot_id=snapshot_id)
    more = len(records) > limit
    records = records[-limit:]
    previous = None
    if records and records[0]["role"] == "assistant":
        with get_connection() as conn:
            row = conn.execute("SELECT role, content FROM messages WHERE session_id = ? AND id < ? ORDER BY id DESC LIMIT 1",
                               (session_id, records[0]["id"])).fetchone()
            if row and row["role"] == "user":
                previous = row["content"]
    return {"messages": records, "has_more": more,
            "next_before_id": records[0]["id"] if more else None,
            "snapshot_id": snapshot_id, "total_messages": total, "graph_context": previous}


def get_message_record(session_id: str, message_id: int) -> dict | None:
    """Load one message only when it belongs to the requested chat."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_id, role, content, finish_reason,
                   continuation_count, continuation_allowed, source_metadata, diagram_spec, attachment_context
            FROM messages
            WHERE session_id = ? AND id = ?
            """,
            (session_id, message_id),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "role": row["role"],
        "content": row["content"],
        "finish_reason": row["finish_reason"],
        "continuation_count": row["continuation_count"],
        "can_continue": bool(row["continuation_allowed"]),
        "sources": _load_source_metadata(row["source_metadata"]),
        "diagram": _load_diagram_spec(row["diagram_spec"]),
        "attachments": public_attachments(_attachment_context(row["attachment_context"])),
    }


def _load_source_metadata(raw_value: str | None) -> list[dict]:
    """Read saved source labels without allowing broken JSON to break chat history."""
    try:
        sources = json.loads(raw_value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict)][:3]


def _load_diagram_spec(raw_value: str | None) -> dict | None:
    """Read diagram data without allowing broken saved JSON to break history."""
    try:
        diagram = json.loads(raw_value or "null")
    except (TypeError, json.JSONDecodeError):
        return None
    return diagram if isinstance(diagram, dict) else None


def load_messages_through(session_id: str, message_id: int, limit: int = 40) -> list[dict]:
    """Load AI-ready conversation messages ending at one saved message."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, attachment_context
            FROM messages
            WHERE session_id = ? AND id <= ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, message_id, limit),
        ).fetchall()
    return [_provider_message(row) for row in reversed(rows)]


def replace_message_with_continuation(
    session_id: str,
    message_id: int,
    content: str,
    finish_reason: str,
    continuation_allowed: bool,
    max_continuations: int,
) -> bool:
    """Atomically append one approved continuation to an assistant message."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE messages
            SET content = ?,
                finish_reason = ?,
                continuation_count = continuation_count + 1,
                continuation_allowed = ?
            WHERE session_id = ?
              AND id = ?
              AND role = 'assistant'
              AND continuation_count < ?
            """,
            (
                content,
                finish_reason,
                int(continuation_allowed),
                session_id,
                message_id,
                max_continuations,
            ),
        )
        conn.commit()
        return cursor.rowcount == 1


def clear_messages(session_id: str):
    """Delete all messages for a session."""
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM token_usage WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_stats WHERE session_id = ?", (session_id,))
        conn.commit()


# ===== Generated images =====

def save_generated_image_record(
    *,
    image_id: str,
    owner_id: str,
    session_id: str,
    message_id: int | None,
    prompt: str,
    image_request: dict,
    review: dict,
    provider: str,
    model: str,
    mime_type: str,
    width: int,
    height: int,
    local_filename: str,
) -> None:
    """Save image metadata without putting the image bytes in SQLite."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO generated_images (
                id, owner_id, session_id, message_id, prompt,
                image_request_json, review_json, provider, model,
                mime_type, width, height, local_filename
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                image_id,
                owner_id,
                session_id,
                message_id,
                prompt,
                json.dumps(image_request, ensure_ascii=True),
                json.dumps(review, ensure_ascii=True),
                provider,
                model,
                mime_type,
                width,
                height,
                local_filename,
            ),
        )
        conn.commit()


def get_generated_image_record(image_id: str, owner_id: str) -> dict | None:
    """Load one image record only when it belongs to the requesting owner."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, owner_id, session_id, message_id, prompt,
                   image_request_json, review_json, provider, model,
                   mime_type, width, height, local_filename, created_at
            FROM generated_images
            WHERE id = ? AND owner_id = ?
            """,
            (image_id, owner_id),
        ).fetchone()
    return _generated_image_row(row)


def set_generated_image_message_id(
    image_id: str,
    owner_id: str,
    message_id: int,
) -> bool:
    """Attach an owned image to its saved assistant message."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE generated_images
            SET message_id = ?
            WHERE id = ? AND owner_id = ?
            """,
            (message_id, image_id, owner_id),
        )
        conn.commit()
    return cursor.rowcount == 1


def list_generated_image_records(owner_id: str, session_id: str) -> list[dict]:
    """List owned images for one chat from oldest to newest."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, owner_id, session_id, message_id, prompt,
                   image_request_json, review_json, provider, model,
                   mime_type, width, height, local_filename, created_at
            FROM generated_images
            WHERE owner_id = ? AND session_id = ?
            ORDER BY created_at, id
            """,
            (owner_id, session_id),
        ).fetchall()
    return [_generated_image_row(row) for row in rows]


def list_generated_image_filenames(owner_id: str) -> set[str]:
    """Return the server-created filenames currently owned by one browser user."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT local_filename FROM generated_images WHERE owner_id = ?",
            (owner_id,),
        ).fetchall()
    return {str(row["local_filename"]) for row in rows}


def pop_generated_image_record(image_id: str, owner_id: str) -> dict | None:
    """Atomically remove and return one owned image record."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, owner_id, session_id, message_id, prompt,
                   image_request_json, review_json, provider, model,
                   mime_type, width, height, local_filename, created_at
            FROM generated_images
            WHERE id = ? AND owner_id = ?
            """,
            (image_id, owner_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "DELETE FROM generated_images WHERE id = ? AND owner_id = ?",
            (image_id, owner_id),
        )
        conn.commit()
    return _generated_image_row(row)


def pop_generated_images_for_session(owner_id: str, session_id: str) -> list[dict]:
    """Atomically remove and return every owned image record for one chat."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, owner_id, session_id, message_id, prompt,
                   image_request_json, review_json, provider, model,
                   mime_type, width, height, local_filename, created_at
            FROM generated_images
            WHERE owner_id = ? AND session_id = ?
            """,
            (owner_id, session_id),
        ).fetchall()
        conn.execute(
            "DELETE FROM generated_images WHERE owner_id = ? AND session_id = ?",
            (owner_id, session_id),
        )
        conn.commit()
    return [_generated_image_row(row) for row in rows]


def _generated_image_row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "session_id": row["session_id"],
        "message_id": row["message_id"],
        "prompt": row["prompt"],
        "image_request": _load_json_object(row["image_request_json"]),
        "review": _load_json_object(row["review_json"]),
        "provider": row["provider"],
        "model": row["model"],
        "mime_type": row["mime_type"],
        "width": row["width"],
        "height": row["height"],
        "local_filename": row["local_filename"],
        "created_at": row["created_at"],
    }


def _load_json_object(raw_value: str | None) -> dict:
    try:
        value = json.loads(raw_value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


# ===== Question counter =====

def increment_question_count(session_id: str) -> int:
    """Increment and return the question count for this session."""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO session_stats (session_id, question_count, topics_seen)
            VALUES (?, 1, '')
            ON CONFLICT(session_id) DO UPDATE SET question_count = question_count + 1
        """, (session_id,))
        conn.commit()
        row = conn.execute(
            "SELECT question_count FROM session_stats WHERE session_id = ?",
            (session_id,)
        ).fetchone()
    return row[0] if row else 1


# ===== Topic tracker =====

TOPIC_KEYWORDS = {
    "Algebra":      ["equation", "solve", "factor", "polynomial", "inequality", "variable", "linear", "quadratic"],
    "Geometry":     ["area", "volume", "triangle", "circle", "angle", "perimeter", "polygon", "proof", "coordinate"],
    "Trigonometry": ["sin", "cos", "tan", "trig", "radian", "degree", "unit circle", "identity", "secant"],
    "Calculus":     ["derivative", "integral", "limit", "differentiate", "integrate", "rate of change", "slope"],
    "Statistics":   ["mean", "median", "mode", "probability", "distribution", "standard deviation", "variance"],
}


def detect_topic(message: str) -> str | None:
    """Detect the math topic from the user's message."""
    msg_lower = message.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return topic
    return None


def add_topic(session_id: str, topic: str):
    """Add a topic to the session's seen topics list (no duplicates)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT topics_seen FROM session_stats WHERE session_id = ?",
            (session_id,)
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO session_stats (session_id, question_count, topics_seen) VALUES (?, 0, ?)",
                (session_id, topic)
            )
        else:
            existing = row[0].split(",") if row[0] else []
            if topic not in existing:
                existing.append(topic)
                conn.execute(
                    "UPDATE session_stats SET topics_seen = ? WHERE session_id = ?",
                    (",".join(existing), session_id)
                )
        conn.commit()


def get_topics(session_id: str) -> list[str]:
    """Get the list of topics covered in this session."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT topics_seen FROM session_stats WHERE session_id = ?",
            (session_id,)
        ).fetchone()
    if row and row[0]:
        return [t for t in row[0].split(",") if t]
    return []


# ===== Last plotted equation =====

def save_last_equation(session_id: str, equation: str, *, only_if_active: bool = False):
    """Remember the most recently plotted equation for this session."""
    with get_connection() as conn:
        if only_if_active:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM chat_sessions WHERE session_id = ? AND deleted = 0",
                                (session_id,)).fetchone():
                return
        conn.execute("""
            INSERT INTO session_stats (session_id, question_count, topics_seen, last_equation)
            VALUES (?, 0, '', ?)
            ON CONFLICT(session_id) DO UPDATE SET last_equation = ?
        """, (session_id, equation, equation))
        conn.commit()


def get_last_equation(session_id: str) -> str | None:
    """Retrieve the last plotted equation for this session, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_equation FROM session_stats WHERE session_id = ?",
            (session_id,)
        ).fetchone()
    if row and row[0]:
        return row[0]
    return None


# ===== Session listing =====

def get_session_title_context(session_id: str) -> dict | None:
    """Read the actual first exchange, even in a long-running chat."""
    with get_connection() as conn:
        first = conn.execute(
            "SELECT id, content FROM messages WHERE session_id = ? AND role = 'user' ORDER BY id LIMIT 1",
            (session_id,),
        ).fetchone()
        if first is None:
            return None
        stats = conn.execute(
            "SELECT title FROM session_stats WHERE session_id = ?", (session_id,),
        ).fetchone()
        answer = conn.execute(
            "SELECT content FROM messages "
            "WHERE session_id = ? AND role = 'assistant' AND id > ? "
            "AND COALESCE(finish_reason, '') != 'error' AND TRIM(content) != '' ORDER BY id LIMIT 1",
            (session_id, first["id"]),
        ).fetchone()
    messages = [{"role": "user", "content": first["content"]}]
    if answer:
        messages.append({"role": "assistant", "content": answer["content"]})
    return {
        "first_message_id": first["id"],
        "title": stats["title"] if stats else "",
        "messages": messages,
    }


def save_session_title(session_id: str, first_message_id: int, title: str, tokens_used: int) -> bool:
    """Save once, without restoring a chat deleted or cleared during generation."""
    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        first = conn.execute(
            "SELECT id FROM messages WHERE session_id = ? AND role = 'user' ORDER BY id LIMIT 1",
            (session_id,),
        ).fetchone()
        if first is None or first["id"] != first_message_id:
            return False
        if tokens_used:
            conn.execute(
                "INSERT INTO token_usage (session_id, tokens) VALUES (?, ?)",
                (session_id, tokens_used),
            )
        if not title:
            return False
        cursor = conn.execute(
            "INSERT INTO session_stats (session_id, title) VALUES (?, ?) "
            "ON CONFLICT(session_id) DO UPDATE SET title = excluded.title WHERE session_stats.title = ''",
            (session_id, title),
        )
        return cursor.rowcount == 1


def make_session_title(message: str) -> str:
    """Provide a readable fallback while an AI title is unavailable."""
    title = re.sub(r"\s+", " ", message).strip()
    if title.lower().startswith("i want to prepare for a math competition"):
        return "Math competition prep"
    title = re.sub(r"^please\s+", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^(?:can you|could you|would you)\s+", "", title, flags=re.IGNORECASE)
    title = title.rstrip("?.! ")
    if not title:
        return "New conversation"
    title = title[:1].upper() + title[1:]
    if len(title) > 42:
        return title[:39].rstrip() + "..."
    return title

def list_all_sessions(owner_id: str | None = None, mode: str | None = None) -> list[dict]:
    """Unfiltered reads are for local maintenance only; HTTP callers supply owner/mode."""
    owned_filter = ""
    parameters = ()
    if owner_id is not None:
        owned_filter = ("WHERE EXISTS (SELECT 1 FROM chat_sessions c WHERE c.session_id = m.session_id "
                        "AND c.owner_id = ? AND c.mode = ? AND c.deleted = 0)")
        parameters = (owner_id, mode)
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                m.session_id,
                (SELECT content FROM messages first
                 WHERE first.session_id = m.session_id AND first.role = 'user'
                 ORDER BY first.id LIMIT 1) AS first_message,
                COALESCE(s.title, '') AS title,
                MAX(CASE WHEN m.role = 'assistant' AND COALESCE(m.finish_reason, '') != 'error'
                         AND TRIM(m.content) != '' THEN 1 ELSE 0 END) AS title_ready,
                COUNT(*) AS message_count,
                MAX(m.created_at) AS last_active
            FROM messages m
            LEFT JOIN session_stats s ON s.session_id = m.session_id
            """ + owned_filter + """
            GROUP BY m.session_id
            ORDER BY last_active DESC
        """, parameters).fetchall()
    sessions = []
    for r in rows:
        preview = r["title"] or make_session_title(r["first_message"] or "")
        sessions.append({
            "session_id": r["session_id"],
            "preview": preview,
            "title_generated": bool(r["title"]),
            "title_ready": bool(r["title_ready"]),
            "message_count": r["message_count"],
            "last_active": r["last_active"],
        })
    return sessions
