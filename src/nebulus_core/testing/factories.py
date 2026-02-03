"""Factory functions for creating test instances of core models."""

from nebulus_core.memory.models import Entity, MemoryItem, Relation


def make_entity(**overrides) -> Entity:
    """Create an Entity with sensible defaults.

    Args:
        **overrides: Fields to override on the Entity.

    Returns:
        A valid Entity instance.
    """
    defaults = {"id": "test-entity", "type": "TestType"}
    defaults.update(overrides)
    return Entity(**defaults)


def make_relation(**overrides) -> Relation:
    """Create a Relation with sensible defaults.

    Args:
        **overrides: Fields to override on the Relation.

    Returns:
        A valid Relation instance.
    """
    defaults = {"source": "src-node", "target": "tgt-node", "relation": "TEST_REL"}
    defaults.update(overrides)
    return Relation(**defaults)


def make_memory_item(**overrides) -> MemoryItem:
    """Create a MemoryItem with sensible defaults.

    Args:
        **overrides: Fields to override on the MemoryItem.

    Returns:
        A valid MemoryItem instance.
    """
    defaults = {"content": "Test memory content"}
    defaults.update(overrides)
    return MemoryItem(**defaults)
