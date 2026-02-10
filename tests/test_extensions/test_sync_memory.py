"""Tests for the ecosystem-watcher sync_memory hook."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the hook script to the import path
HOOK_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "extensions"
    / "ecosystem-watcher"
    / "hooks"
)
sys.path.insert(0, str(HOOK_DIR))

from sync_memory import (  # noqa: E402
    CACHE_TTL_SECONDS,
    _fetch_entries,
    _format_markdown,
    _read_cache,
    _write_cache,
)

from nebulus_core.memory.overlord import OverlordMemory  # noqa: E402


@pytest.fixture
def memory(tmp_path: Path) -> OverlordMemory:
    """Create a memory store with a temp database."""
    return OverlordMemory(db_path=tmp_path / "test_memory.db")


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    """Override cache paths to use temp directory."""
    return tmp_path / ".cache"


PATCH_TARGET = "nebulus_core.memory.overlord.OverlordMemory"


class TestFetchEntries:
    """Tests for _fetch_entries."""

    def test_fetches_update_and_decision_categories(
        self, memory: OverlordMemory
    ) -> None:
        memory.remember("update", "Deployed v2.0", project="nebulus-prime")
        memory.remember("decision", "Use SQLite for memory", project="nebulus-core")
        memory.remember("failure", "Tests broke", project="nebulus-core")

        with patch(PATCH_TARGET, return_value=memory):
            entries = _fetch_entries()

        assert len(entries) == 2
        categories = {e["category"] for e in entries}
        assert categories == {"update", "decision"}

    def test_limits_to_15_entries(self, memory: OverlordMemory) -> None:
        for i in range(20):
            memory.remember("update", f"Update {i}", project="core")

        with patch(PATCH_TARGET, return_value=memory):
            entries = _fetch_entries()

        assert len(entries) == 15

    def test_sorted_newest_first(self, memory: OverlordMemory) -> None:
        memory.remember("update", "First update", project="core")
        memory.remember("update", "Second update", project="core")

        with patch(PATCH_TARGET, return_value=memory):
            entries = _fetch_entries()

        assert "Second" in entries[0]["content"]
        assert "First" in entries[1]["content"]

    def test_handles_missing_database(self) -> None:
        bogus = OverlordMemory(db_path=Path("/tmp/nonexistent_test.db"))
        with patch(PATCH_TARGET, return_value=bogus):
            entries = _fetch_entries()
        assert entries == []

    def test_returns_empty_on_import_error(self) -> None:
        with patch(PATCH_TARGET, side_effect=ImportError("nope")):
            entries = _fetch_entries()
        assert entries == []


class TestCache:
    """Tests for TTL cache read/write."""

    def test_write_and_read_cache(self, cache_dir: Path) -> None:
        cache_file = cache_dir / "memory_snapshot.json"
        with (
            patch("sync_memory.CACHE_DIR", cache_dir),
            patch("sync_memory.CACHE_FILE", cache_file),
        ):
            sample = [{"timestamp": "2026-02-09T10:00:00", "category": "update",
                        "project": "core", "content": "Test"}]
            _write_cache(sample)
            result = _read_cache()
            assert result is not None
            assert result["entries"] == sample

    def test_cache_expires_after_ttl(self, cache_dir: Path) -> None:
        cache_file = cache_dir / "memory_snapshot.json"
        with (
            patch("sync_memory.CACHE_DIR", cache_dir),
            patch("sync_memory.CACHE_FILE", cache_file),
        ):
            sample = [{"timestamp": "2026-02-09T10:00:00", "category": "update",
                        "project": "core", "content": "Old"}]
            _write_cache(sample)

            # Backdate the fetched_at timestamp
            data = json.loads(cache_file.read_text())
            data["fetched_at"] = time.time() - CACHE_TTL_SECONDS - 1
            cache_file.write_text(json.dumps(data))

            result = _read_cache()
            assert result is None

    def test_read_cache_returns_none_when_missing(self, cache_dir: Path) -> None:
        cache_file = cache_dir / "memory_snapshot.json"
        with (
            patch("sync_memory.CACHE_DIR", cache_dir),
            patch("sync_memory.CACHE_FILE", cache_file),
        ):
            assert _read_cache() is None

    def test_read_cache_handles_corrupt_json(self, cache_dir: Path) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "memory_snapshot.json"
        cache_file.write_text("not valid json {{{")
        with (
            patch("sync_memory.CACHE_DIR", cache_dir),
            patch("sync_memory.CACHE_FILE", cache_file),
        ):
            assert _read_cache() is None


class TestFormatMarkdown:
    """Tests for _format_markdown."""

    def test_empty_entries(self) -> None:
        md = _format_markdown([])
        assert "No recent activity" in md
        assert "## Recent Swarm Activity" in md

    def test_formats_entries_with_project(self) -> None:
        entries = [
            {
                "timestamp": "2026-02-09T14:30:00+00:00",
                "category": "update",
                "project": "nebulus-core",
                "content": "Migrated MCP tools",
            }
        ]
        md = _format_markdown(entries)
        assert "## Recent Swarm Activity" in md
        assert "2026-02-09 14:30" in md
        assert "**nebulus-core**" in md
        assert "Migrated MCP tools" in md
        assert "[update]" in md

    def test_formats_ecosystem_wide_entry(self) -> None:
        entries = [
            {
                "timestamp": "2026-02-09T12:00:00+00:00",
                "category": "decision",
                "project": None,
                "content": "Adopt develop-main branching",
            }
        ]
        md = _format_markdown(entries)
        assert "_ecosystem_" in md
        assert "[decision]" in md

    def test_timestamp_trimmed_to_minute(self) -> None:
        entries = [
            {
                "timestamp": "2026-02-09T14:30:45.123456+00:00",
                "category": "update",
                "project": "core",
                "content": "Test",
            }
        ]
        md = _format_markdown(entries)
        # Should not include seconds
        assert "14:30:45" not in md
        assert "2026-02-09 14:30" in md
