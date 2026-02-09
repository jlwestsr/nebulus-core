"""Tests for memory data models."""

import time

from nebulus_core.memory.models import Entity, Relation, MemoryItem, GraphStats


class TestEntity:
    def test_create_entity(self) -> None:
        """Entity can be created with required fields and default properties."""
        e = Entity(id="server-1", type="Server")
        assert e.id == "server-1"
        assert e.type == "Server"
        assert e.properties == {}

    def test_entity_with_properties(self) -> None:
        """Entity accepts custom properties dict."""
        e = Entity(id="srv", type="Server", properties={"ip": "10.0.0.1"})
        assert e.properties["ip"] == "10.0.0.1"


class TestRelation:
    def test_create_relation(self) -> None:
        """Relation can be created with required fields and default weight."""
        r = Relation(source="a", target="b", relation="CONNECTS_TO")
        assert r.source == "a"
        assert r.target == "b"
        assert r.relation == "CONNECTS_TO"
        assert r.weight == 1.0

    def test_custom_weight(self) -> None:
        """Relation accepts custom weight value."""
        r = Relation(source="a", target="b", relation="X", weight=0.5)
        assert r.weight == 0.5


class TestMemoryItem:
    def test_defaults(self) -> None:
        """MemoryItem has sensible defaults for id, timestamp, archived, metadata."""
        m = MemoryItem(content="test content")
        assert m.content == "test content"
        assert m.archived is False
        assert m.metadata == {}
        assert len(m.id) > 0
        assert m.timestamp <= time.time()

    def test_explicit_id(self) -> None:
        """MemoryItem accepts an explicit id override."""
        m = MemoryItem(id="custom-id", content="test")
        assert m.id == "custom-id"


class TestGraphStats:
    def test_create_stats(self) -> None:
        """GraphStats stores node count, edge count, and entity types."""
        s = GraphStats(node_count=5, edge_count=3, entity_types=["Server", "Person"])
        assert s.node_count == 5
        assert s.edge_count == 3
        assert "Server" in s.entity_types
