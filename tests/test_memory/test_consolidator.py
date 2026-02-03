"""Tests for the memory consolidator."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nebulus_core.memory.consolidator import Consolidator
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import MemoryItem


@pytest.fixture
def graph(tmp_path):
    return GraphStore(storage_path=tmp_path / "graph.json")


@pytest.fixture
def mock_episodic():
    ep = MagicMock()
    ep.get_unarchived.return_value = [
        MemoryItem(id="m1", content="Server prod-1 has IP 10.0.0.1"),
        MemoryItem(id="m2", content="Alice owns the prod-1 server"),
    ]
    ep.mark_archived = MagicMock()
    return ep


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm_response = json.dumps(
        {
            "entities": [
                {"id": "prod-1", "type": "Server"},
                {"id": "10.0.0.1", "type": "IP"},
            ],
            "relations": [
                {
                    "source": "prod-1",
                    "target": "10.0.0.1",
                    "relation": "HAS_IP",
                }
            ],
        }
    )
    llm.chat.return_value = llm_response
    return llm


@pytest.fixture
def consolidator(mock_episodic, graph, mock_llm):
    return Consolidator(
        episodic=mock_episodic,
        graph=graph,
        llm=mock_llm,
        model="test-model",
    )


class TestConsolidator:
    def test_consolidate_processes_memories(self, consolidator, mock_episodic):
        result = consolidator.consolidate()
        assert "2" in result  # processed 2 memories
        mock_episodic.mark_archived.assert_called_once_with(["m1", "m2"])

    def test_consolidate_updates_graph(self, consolidator, graph):
        consolidator.consolidate()
        stats = graph.get_stats()
        # Each memory produces same 2 entities (idempotent adds)
        assert stats.node_count >= 2
        assert stats.edge_count >= 1

    def test_consolidate_no_memories(self, graph, mock_llm):
        ep = MagicMock()
        ep.get_unarchived.return_value = []
        c = Consolidator(episodic=ep, graph=graph, llm=mock_llm, model="m")
        result = c.consolidate()
        assert "No" in result or "0" in result

    def test_consolidate_llm_returns_invalid_json(
        self, mock_episodic, graph
    ):
        llm = MagicMock()
        llm.chat.return_value = "I cannot extract entities from this."
        c = Consolidator(
            episodic=mock_episodic, graph=graph, llm=llm, model="m"
        )
        result = c.consolidate()
        # Should not crash, just skip
        assert result is not None

    def test_consolidate_uses_llm_chat(self, consolidator, mock_llm):
        consolidator.consolidate()
        assert mock_llm.chat.call_count == 2  # once per memory
        call_kwargs = mock_llm.chat.call_args_list[0][1]
        assert call_kwargs["model"] == "test-model"
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
