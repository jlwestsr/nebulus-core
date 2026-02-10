"""Cross-project memory store for the Overlord.

Pure SQLite store for structured observations like release events,
failure patterns, and configuration decisions. No embeddings — just
fast filtered text search for operational memory.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional


@dataclass
class MemoryEntry:
    """A single memory observation."""

    id: str
    timestamp: str
    category: str
    project: Optional[str]
    content: str
    metadata: dict = field(default_factory=dict)


VALID_CATEGORIES = frozenset(
    {
        "pattern",
        "preference",
        "relation",
        "decision",
        "failure",
        "release",
        "update",
        "dispatch",
    }
)

DEFAULT_DB_PATH = Path.home() / ".atom" / "overlord" / "memory.db"


class OverlordMemory:
    """Cross-project memory store backed by SQLite."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize the memory store.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/.atom/overlord/memory.db.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create the memory table and indexes if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    project TEXT,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_project
                ON memory(project)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_category
                ON memory(category)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_timestamp
                ON memory(timestamp DESC)
                """
            )

    def remember(
        self,
        category: str,
        content: str,
        project: Optional[str] = None,
        **metadata: object,
    ) -> str:
        """Store an observation.

        Args:
            category: One of: decision, dispatch, failure, pattern, preference, relation, release, update.
            content: Human-readable observation text.
            project: Which project this relates to (None = ecosystem-wide).
            **metadata: Arbitrary key-value pairs stored as JSON.

        Returns:
            The UUID of the created memory entry.

        Raises:
            ValueError: If category is not valid.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memory (id, timestamp, category, project, content, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry_id,
                    timestamp,
                    category,
                    project,
                    content,
                    json.dumps(metadata),
                ),
            )

        return entry_id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        project: Optional[str] = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """Search memories by content text with optional filters.

        Args:
            query: Text to search for (SQLite LIKE pattern).
            category: Optional category filter.
            project: Optional project filter.
            limit: Maximum number of results.

        Returns:
            List of matching MemoryEntry objects, newest first.
        """
        if query:
            sql = "SELECT * FROM memory WHERE content LIKE ?"
            params: list[object] = [f"%{query}%"]
        else:
            sql = "SELECT * FROM memory WHERE 1=1"
            params: list[object] = []

        if category:
            sql += " AND category = ?"
            params.append(category)
        if project:
            sql += " AND project = ?"
            params.append(project)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def forget(self, entry_id: str) -> bool:
        """Delete a specific memory.

        Args:
            entry_id: UUID of the memory to delete.

        Returns:
            True if the entry was found and deleted, False otherwise.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM memory WHERE id = ?", (entry_id,))
            return cursor.rowcount > 0

    def get_project_history(self, project: str, limit: int = 20) -> list[MemoryEntry]:
        """Get all memories for a project, newest first.

        Args:
            project: Project name.
            limit: Maximum number of results.

        Returns:
            List of MemoryEntry objects.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memory WHERE project = ? ORDER BY timestamp DESC LIMIT ?",
                (project, limit),
            ).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Get most recent memories across all projects.

        Args:
            limit: Maximum number of results.

        Returns:
            List of MemoryEntry objects, newest first.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memory ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def prune(self, older_than_days: int) -> int:
        """Delete entries older than the specified number of days.

        Args:
            older_than_days: Delete entries older than this many days.

        Returns:
            Number of entries deleted.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=older_than_days)
        ).isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM memory WHERE timestamp < ?", (cutoff,))
            return cursor.rowcount

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert a database row to a MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            timestamp=row["timestamp"],
            category=row["category"],
            project=row["project"],
            content=row["content"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )
