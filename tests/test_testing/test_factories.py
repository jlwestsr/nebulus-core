"""Tests for shared test factories."""

from nebulus_core.memory.models import Entity, MemoryItem, Relation
from nebulus_core.testing.factories import make_entity, make_memory_item, make_relation


class TestFactories:
    def test_make_entity_defaults(self):
        e = make_entity()
        assert isinstance(e, Entity)
        assert e.id
        assert e.type

    def test_make_entity_overrides(self):
        e = make_entity(id="srv-1", type="Server")
        assert e.id == "srv-1"
        assert e.type == "Server"

    def test_make_relation_defaults(self):
        r = make_relation()
        assert isinstance(r, Relation)
        assert r.source
        assert r.target
        assert r.relation

    def test_make_relation_overrides(self):
        r = make_relation(source="a", target="b", relation="LINKS")
        assert r.source == "a"
        assert r.target == "b"
        assert r.relation == "LINKS"

    def test_make_memory_item_defaults(self):
        m = make_memory_item()
        assert isinstance(m, MemoryItem)
        assert m.content
        assert m.id
        assert m.archived is False

    def test_make_memory_item_overrides(self):
        m = make_memory_item(content="custom", archived=True)
        assert m.content == "custom"
        assert m.archived is True
