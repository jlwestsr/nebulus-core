"""Tests for the Overlord cross-project memory store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nebulus_core.memory.overlord import OverlordMemory


@pytest.fixture
def memory(tmp_path: Path) -> OverlordMemory:
    """Create a memory store with a temp database."""
    return OverlordMemory(db_path=tmp_path / "test_memory.db")


class TestRememberAndSearch:
    """Tests for remember + search round-trip."""

    def test_remember_returns_uuid(self, memory: OverlordMemory) -> None:
        entry_id = memory.remember("release", "Core v0.1.0 released")
        assert len(entry_id) == 36  # UUID format

    def test_search_finds_by_content(self, memory: OverlordMemory) -> None:
        memory.remember("release", "Core v0.1.0 released", project="nebulus-core")
        results = memory.search("v0.1.0")
        assert len(results) == 1
        assert results[0].content == "Core v0.1.0 released"
        assert results[0].category == "release"
        assert results[0].project == "nebulus-core"

    def test_search_filters_by_category(self, memory: OverlordMemory) -> None:
        memory.remember("release", "Core released")
        memory.remember("failure", "Tests failed")
        results = memory.search("", category="release")
        assert len(results) == 1
        assert results[0].category == "release"

    def test_search_filters_by_project(self, memory: OverlordMemory) -> None:
        memory.remember("release", "Core released", project="core")
        memory.remember("release", "Prime released", project="prime")
        results = memory.search("released", project="core")
        assert len(results) == 1
        assert results[0].project == "core"

    def test_search_respects_limit(self, memory: OverlordMemory) -> None:
        for i in range(10):
            memory.remember("pattern", f"Pattern {i}")
        results = memory.search("Pattern", limit=3)
        assert len(results) == 3

    def test_search_returns_newest_first(self, memory: OverlordMemory) -> None:
        memory.remember("pattern", "First")
        memory.remember("pattern", "Second")
        results = memory.search("")
        assert results[0].content == "Second"
        assert results[1].content == "First"

    def test_invalid_category_raises(self, memory: OverlordMemory) -> None:
        with pytest.raises(ValueError, match="Invalid category"):
            memory.remember("bogus", "Should fail")

    def test_metadata_stored_and_retrieved(self, memory: OverlordMemory) -> None:
        memory.remember(
            "decision", "Use SQLite for memory", tags=["architecture", "storage"]
        )
        results = memory.search("SQLite")
        assert results[0].metadata["tags"] == ["architecture", "storage"]


class TestForget:
    """Tests for OverlordMemory.forget."""

    def test_forget_deletes_entry(self, memory: OverlordMemory) -> None:
        entry_id = memory.remember("pattern", "Temporary observation")
        assert memory.forget(entry_id) is True
        results = memory.search("Temporary")
        assert len(results) == 0

    def test_forget_nonexistent_returns_false(self, memory: OverlordMemory) -> None:
        assert memory.forget("nonexistent-uuid") is False


class TestProjectHistory:
    """Tests for OverlordMemory.get_project_history."""

    def test_returns_only_matching_project(self, memory: OverlordMemory) -> None:
        memory.remember("release", "Core v1", project="core")
        memory.remember("release", "Prime v1", project="prime")
        history = memory.get_project_history("core")
        assert len(history) == 1
        assert history[0].project == "core"

    def test_ordering_newest_first(self, memory: OverlordMemory) -> None:
        memory.remember("pattern", "Old", project="core")
        memory.remember("pattern", "New", project="core")
        history = memory.get_project_history("core")
        assert history[0].content == "New"


class TestGetRecent:
    """Tests for OverlordMemory.get_recent."""

    def test_returns_across_projects(self, memory: OverlordMemory) -> None:
        memory.remember("release", "Core event", project="core")
        memory.remember("failure", "Prime event", project="prime")
        recent = memory.get_recent()
        assert len(recent) == 2

    def test_respects_limit(self, memory: OverlordMemory) -> None:
        for i in range(5):
            memory.remember("pattern", f"Item {i}")
        recent = memory.get_recent(limit=2)
        assert len(recent) == 2


class TestPrune:
    """Tests for OverlordMemory.prune."""

    def test_prune_deletes_old_entries(self, memory: OverlordMemory) -> None:
        # Insert an entry with a timestamp 100 days ago
        old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        import sqlite3

        conn = sqlite3.connect(str(memory.db_path))
        conn.execute(
            "INSERT INTO memory (id, timestamp, category, content, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            ("old-entry", old_ts, "pattern", "Ancient observation", "{}"),
        )
        conn.commit()
        conn.close()

        # Also add a recent entry
        memory.remember("pattern", "Fresh observation")

        pruned = memory.prune(older_than_days=30)
        assert pruned == 1

        remaining = memory.get_recent()
        assert len(remaining) == 1
        assert remaining[0].content == "Fresh observation"

    def test_prune_returns_zero_when_nothing_old(self, memory: OverlordMemory) -> None:
        memory.remember("pattern", "Recent entry")
        assert memory.prune(older_than_days=30) == 0


class TestEcosystemWideMemory:
    """Tests for memories without a project (ecosystem-wide)."""

    def test_remember_without_project(self, memory: OverlordMemory) -> None:
        memory.remember("decision", "Adopt develop-main branching")
        results = memory.search("develop-main")
        assert len(results) == 1
        assert results[0].project is None
