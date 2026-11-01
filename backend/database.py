"""SQLite persistence layer for LocalGPT.

The database is created automatically on first use. All access goes through
short-lived connections which keeps the layer thread-safe under Flask's
threaded development server.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL DEFAULT 'New chat',
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role            TEXT    NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages (conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations (updated_at DESC);
"""

DEFAULT_TITLE = "New chat"


def utcnow() -> str:
    """ISO-8601 UTC timestamp with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    # -- connection helpers -------------------------------------------------
    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.path), timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self.connection() as conn:
            conn.executescript(SCHEMA)

    # -- conversations ------------------------------------------------------
    def create_conversation(self, title: str = DEFAULT_TITLE) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO conversations (title, created_at, updated_at) "
                "VALUES (?, ?, ?)",
                (title, now, now),
            )
            return {
                "id": cur.lastrowid,
                "title": title,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
            }

    def list_conversations(self) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) AS message_count
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id
                ORDER BY c.updated_at DESC, c.id DESC
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: int) -> Optional[dict[str, Any]]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
                (conversation_id,),
            ).fetchone()
            return dict(row) if row else None

    def rename_conversation(self, conversation_id: int, title: str) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, utcnow(), conversation_id),
            )
            return cur.rowcount > 0

    def touch_conversation(self, conversation_id: int) -> None:
        with self.connection() as conn:
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utcnow(), conversation_id),
            )

    def delete_conversation(self, conversation_id: int) -> bool:
        with self.connection() as conn:
            cur = conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            return cur.rowcount > 0

    def clear_messages(self, conversation_id: int) -> bool:
        with self.connection() as conn:
            exists = conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if not exists:
                return False
            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,)
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (utcnow(), conversation_id),
            )
            return True

    # -- messages -----------------------------------------------------------
    def add_message(self, conversation_id: int, role: str, content: str) -> dict[str, Any]:
        now = utcnow()
        with self.connection() as conn:
            cur = conn.execute(
                "INSERT INTO messages (conversation_id, role, content, created_at) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
            return {
                "id": cur.lastrowid,
                "conversation_id": conversation_id,
                "role": role,
                "content": content,
                "created_at": now,
            }

    def get_messages(self, conversation_id: int) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id, conversation_id, role, content, created_at "
                "FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conversation_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_conversation_with_messages(
        self, conversation_id: int
    ) -> Optional[dict[str, Any]]:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            return None
        conversation["messages"] = self.get_messages(conversation_id)
        return conversation

    def message_count(self, conversation_id: int) -> int:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            return int(row["n"]) if row else 0
