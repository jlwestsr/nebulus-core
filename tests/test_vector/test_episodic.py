"""Tests for the episodic memory layer."""

from unittest.mock import MagicMock

import pytest

from nebulus_core.memory.models import MemoryItem
from nebulus_core.vector.episodic import EpisodicMemory


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={"documents": [["doc1", "doc2"]]})
    collection.get = MagicMock(
        return_value={
            "ids": ["id1", "id2"],
            "documents": ["content1", "content2"],
            "metadatas": [
                {"timestamp": 1.0, "archived": False},
                {"timestamp": 2.0, "archived": False},
            ],
        }
    )
    collection.update = MagicMock()
    return collection


@pytest.fixture
def mock_vector_client(mock_collection):
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def episodic(mock_vector_client):
    return EpisodicMemory(mock_vector_client)


class TestEpisodicMemory:
    def test_init_creates_collection(self, mock_vector_client):
        EpisodicMemory(mock_vector_client)
        mock_vector_client.get_or_create_collection.assert_called_once_with(
            "ltm_episodic_memory"
        )

    def test_custom_collection_name(self, mock_vector_client):
        EpisodicMemory(mock_vector_client, collection_name="custom")
        mock_vector_client.get_or_create_collection.assert_called_once_with("custom")

    def test_add_memory(self, episodic, mock_collection):
        item = MemoryItem(id="test-id", content="hello world")
        episodic.add_memory(item)
        mock_collection.add.assert_called_once()
        call_kwargs = mock_collection.add.call_args[1]
        assert call_kwargs["ids"] == ["test-id"]
        assert call_kwargs["documents"] == ["hello world"]

    def test_query(self, episodic, mock_collection):
        results = episodic.query("search text", n_results=3)
        mock_collection.query.assert_called_once_with(
            query_texts=["search text"], n_results=3
        )
        assert results == ["doc1", "doc2"]

    def test_get_unarchived(self, episodic, mock_collection):
        items = episodic.get_unarchived(n_results=10)
        mock_collection.get.assert_called_once_with(where={"archived": False}, limit=10)
        assert len(items) == 2
        assert items[0].id == "id1"
        assert items[0].content == "content1"

    def test_mark_archived(self, episodic, mock_collection):
        mock_collection.get.return_value = {
            "ids": ["id1"],
            "documents": ["c"],
            "metadatas": [{"archived": False}],
        }
        episodic.mark_archived(["id1"])
        mock_collection.update.assert_called_once()
        call_kwargs = mock_collection.update.call_args[1]
        assert call_kwargs["metadatas"][0]["archived"] is True
