#!/usr/bin/env python3
"""BeforeAgent hook: inject recent Overlord memory into Gemini context.

Reads stdin for the hook input JSON, fetches the last 15 update/decision
entries from OverlordMemory, caches with a 5-minute TTL, and writes
the hookSpecificOutput JSON to stdout.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Cache location relative to extension directory
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "memory_snapshot.json"
CACHE_TTL_SECONDS = 300  # 5 minutes
FETCH_LIMIT = 15
FETCH_CATEGORIES = ("update", "decision")


def _log(msg: str) -> None:
    """Write diagnostic messages to stderr (never stdout)."""
    print(f"[ecosystem-watcher] {msg}", file=sys.stderr)


def _read_cache() -> dict | None:
    """Return cached snapshot if it exists and is fresh, else None."""
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text())
        if time.time() - data.get("fetched_at", 0) < CACHE_TTL_SECONDS:
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _write_cache(entries: list[dict]) -> None:
    """Persist snapshot to disk with current timestamp."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps({"fetched_at": time.time(), "entries": entries}, indent=2)
    )


def _fetch_entries() -> list[dict]:
    """Fetch recent update + decision entries from OverlordMemory."""
    try:
        from nebulus_core.memory.overlord import OverlordMemory

        mem = OverlordMemory()
        results: list[dict] = []
        for cat in FETCH_CATEGORIES:
            hits = mem.search("", category=cat, limit=FETCH_LIMIT)
            for e in hits:
                results.append(
                    {
                        "timestamp": e.timestamp,
                        "category": e.category,
                        "project": e.project,
                        "content": e.content,
                    }
                )
        # Sort newest first across categories, trim to limit
        results.sort(key=lambda r: r["timestamp"], reverse=True)
        return results[:FETCH_LIMIT]
    except Exception as exc:
        _log(f"Failed to fetch memory: {exc}")
        return []


def _format_markdown(entries: list[dict]) -> str:
    """Render entries as a token-efficient Markdown list."""
    if not entries:
        return "## Recent Swarm Activity\n_No recent activity found._"

    lines = ["## Recent Swarm Activity"]
    for e in entries:
        ts = e["timestamp"][:16].replace("T", " ")  # trim to minute
        proj = f"**{e['project']}**" if e.get("project") else "_ecosystem_"
        lines.append(f"- `{ts}` [{e['category']}] {proj}: {e['content']}")
    return "\n".join(lines)


def main() -> None:
    """Entry point: read hook input, resolve memory, emit context."""
    # Consume stdin (required by hook protocol)
    try:
        json.loads(sys.stdin.read())
    except Exception:
        pass

    # Try cache first
    cached = _read_cache()
    if cached is not None:
        entries = cached["entries"]
        _log(f"Using cached snapshot ({len(entries)} entries)")
    else:
        entries = _fetch_entries()
        _write_cache(entries)
        _log(f"Fetched {len(entries)} entries from OverlordMemory")

    markdown = _format_markdown(entries)

    output = {
        "hookSpecificOutput": {
            "additionalContext": f"\n{markdown}\n",
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
