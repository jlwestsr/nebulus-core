"""Knowledge graph and memory consolidation."""

from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, GraphStats, MemoryItem, Relation


def __getattr__(name: str):
    """Lazy-import Consolidator to break circular import with vector.episodic."""
    if name == "Consolidator":
        from nebulus_core.memory.consolidator import Consolidator

        return Consolidator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Consolidator",
    "Entity",
    "GraphStats",
    "GraphStore",
    "MemoryItem",
    "Relation",
]
