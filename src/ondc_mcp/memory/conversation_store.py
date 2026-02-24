"""SQLite-backed conversation memory store."""

import os
from datetime import datetime, timezone
from typing import Any

import aiosqlite


class ConversationStore:
    """Async SQLite store for multi-turn conversation history."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create the database and messages table if they don't exist."""
        os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id        INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                role       TEXT NOT NULL,
                content    TEXT NOT NULL,
                timestamp  TEXT NOT NULL
            )
        """)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_session ON messages (session_id)"
        )
        await self._db.commit()

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None

    async def save_message(self, session_id: str, role: str, content: str) -> None:
        """Persist a single message to the store.

        Args:
            session_id: Conversation/session identifier
            role: One of "user", "assistant", "tool"
            content: Message text
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, timestamp),
        )
        await self._db.commit()

    async def get_history(
        self, session_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return the last *limit* messages for a session, oldest first.

        Args:
            session_id: Conversation/session identifier
            limit: Maximum number of messages to return

        Returns:
            List of {"role", "content", "timestamp"} dicts
        """
        async with self._db.execute(
            """
            SELECT role, content, timestamp
            FROM messages
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        # Reverse so messages are in chronological order
        return [
            {"role": row[0], "content": row[1], "timestamp": row[2]}
            for row in reversed(rows)
        ]

    async def list_sessions(self) -> list[str]:
        """Return all distinct session IDs."""
        async with self._db.execute(
            "SELECT DISTINCT session_id FROM messages ORDER BY session_id"
        ) as cursor:
            rows = await cursor.fetchall()
        return [row[0] for row in rows]
