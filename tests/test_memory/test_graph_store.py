"""Tests for the knowledge graph store."""

from pathlib import Path

import pytest

from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, Relation


@pytest.fixture
def graph_path(tmp_path):
    return tmp_path / "test_graph.json"


@pytest.fixture
def graph(graph_path):
    return GraphStore(storage_path=graph_path)


class TestGraphStore:
    def test_empty_graph_stats(self, graph):
        stats = graph.get_stats()
        assert stats.node_count == 0
        assert stats.edge_count == 0
        assert stats.entity_types == []

    def test_add_entity(self, graph):
        entity = Entity(id="srv-1", type="Server")
        graph.add_entity(entity)
        stats = graph.get_stats()
        assert stats.node_count == 1
        assert "Server" in stats.entity_types

    def test_add_relation(self, graph):
        graph.add_entity(Entity(id="a", type="Server"))
        graph.add_entity(Entity(id="b", type="Database"))
        graph.add_relation(
            Relation(source="a", target="b", relation="CONNECTS_TO")
        )
        stats = graph.get_stats()
        assert stats.edge_count == 1

    def test_add_relation_auto_creates_nodes(self, graph):
        graph.add_relation(
            Relation(source="x", target="y", relation="LINKS")
        )
        stats = graph.get_stats()
        assert stats.node_count == 2
        assert stats.edge_count == 1

    def test_get_neighbors(self, graph):
        graph.add_entity(Entity(id="a", type="T"))
        graph.add_entity(Entity(id="b", type="T"))
        graph.add_relation(
            Relation(source="a", target="b", relation="REL")
        )
        neighbors = graph.get_neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0] == ("REL", "b")

    def test_get_neighbors_unknown_node(self, graph):
        assert graph.get_neighbors("nonexistent") == []

    def test_persistence(self, graph_path):
        g1 = GraphStore(storage_path=graph_path)
        g1.add_entity(Entity(id="persistent", type="Test"))
        del g1

        g2 = GraphStore(storage_path=graph_path)
        stats = g2.get_stats()
        assert stats.node_count == 1

    def test_idempotent_add_entity(self, graph):
        entity = Entity(id="srv", type="Server")
        graph.add_entity(entity)
        graph.add_entity(entity)
        stats = graph.get_stats()
        assert stats.node_count == 1
