"""
Math AI Agent - Database (SQLite conversation persistence)

Stores chat messages so they survive browser refreshes and server restarts.
"""

import sqlite3
import os
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                role      TEXT    NOT NULL,
                content   TEXT    NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT    NOT NULL,
                tokens     INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_stats (
                session_id     TEXT PRIMARY KEY,
                question_count INTEGER DEFAULT 0,
                topics_seen    TEXT DEFAULT '',
                last_equation  TEXT DEFAULT ''
            )
        """)
        # Migrate: add last_equation column if it doesn't exist yet (for existing DBs)
        try:
            conn.execute("ALTER TABLE session_stats ADD COLUMN last_equation TEXT DEFAULT ''")
        except Exception:
            pass  # Column already exists — that's fine
        conn.commit()


def save_message(session_id: str, role: str, content: str):
    """Save a single message to the database."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )
        conn.commit()


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
            SELECT role, content FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    # Reverse so oldest message is first
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_messages(session_id: str):
    """Delete all messages for a session."""
    with get_connection() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM token_usage WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_stats WHERE session_id = ?", (session_id,))
        conn.commit()


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

def save_last_equation(session_id: str, equation: str):
    """Remember the most recently plotted equation for this session."""
    with get_connection() as conn:
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

def list_all_sessions() -> list[dict]:
    """Return all sessions ordered by most recent activity, with a preview title."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                m.session_id,
                MIN(CASE WHEN m.role = 'user' THEN m.content END) AS first_message,
                COUNT(*) AS message_count,
                MAX(m.created_at) AS last_active
            FROM messages m
            GROUP BY m.session_id
            ORDER BY last_active DESC
        """).fetchall()
    sessions = []
    for r in rows:
        preview = r["first_message"] or "New conversation"
        # Truncate long previews
        if len(preview) > 50:
            preview = preview[:47] + "…"
        sessions.append({
            "session_id": r["session_id"],
            "preview": preview,
            "message_count": r["message_count"],
            "last_active": r["last_active"],
        })
    return sessions
