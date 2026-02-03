"""Tests for nebulus_core.intelligence.core.vector_engine."""

from unittest.mock import MagicMock

import pytest

from nebulus_core.intelligence.core.vector_engine import (
    PatternResult,
    SimilarRecord,
    VectorEngine,
)
from nebulus_core.vector.client import VectorClient


@pytest.fixture()
def mock_collection():
    """Return a MagicMock that behaves like a ChromaDB Collection."""
    coll = MagicMock()
    coll.count.return_value = 0
    coll.metadata = {"hnsw:space": "cosine"}
    return coll


@pytest.fixture()
def mock_client(mock_collection):
    """Return a MagicMock VectorClient wired to the mock collection."""
    client = MagicMock(spec=VectorClient)
    client.get_or_create_collection.return_value = mock_collection
    client.list_collections.return_value = ["sales", "products"]
    return client


@pytest.fixture()
def engine(mock_client):
    """Return a VectorEngine backed by mocked dependencies."""
    return VectorEngine(vector_client=mock_client)


# ------------------------------------------------------------------
# embed_records
# ------------------------------------------------------------------


class TestEmbedRecords:
    """Tests for VectorEngine.embed_records."""

    def test_embed_records_empty_list(self, engine, mock_collection):
        """Embedding zero records returns 0 without touching the collection."""
        result = engine.embed_records("sales", [], id_field="id")
        assert result == 0
        mock_collection.upsert.assert_not_called()

    def test_embed_records_single(self, engine, mock_collection):
        """A single record is upserted with correct id, doc, and metadata."""
        records = [{"id": "r1", "name": "Widget", "price": 9.99}]
        result = engine.embed_records("sales", records, id_field="id")

        assert result == 1
        mock_collection.upsert.assert_called_once()
        call_kwargs = mock_collection.upsert.call_args[1]
        assert call_kwargs["ids"] == ["r1"]
        assert len(call_kwargs["documents"]) == 1
        assert "Widget" in call_kwargs["documents"][0]
        assert call_kwargs["metadatas"][0]["price"] == 9.99

    def test_embed_records_multiple(self, engine, mock_collection):
        """Multiple records are batched into a single upsert."""
        records = [
            {"id": "1", "val": "a"},
            {"id": "2", "val": "b"},
            {"id": "3", "val": "c"},
        ]
        result = engine.embed_records("t", records, id_field="id")
        assert result == 3
        call_kwargs = mock_collection.upsert.call_args[1]
        assert call_kwargs["ids"] == ["1", "2", "3"]

    def test_embed_records_none_values(self, engine, mock_collection):
        """None values in records are stored as empty strings in metadata."""
        records = [{"id": "1", "optional": None}]
        engine.embed_records("t", records, id_field="id")
        meta = mock_collection.upsert.call_args[1]["metadatas"][0]
        assert meta["optional"] == ""

    def test_embed_records_non_primitive_values(self, engine, mock_collection):
        """Non-primitive values are stringified in metadata."""
        records = [{"id": "1", "tags": ["a", "b"]}]
        engine.embed_records("t", records, id_field="id")
        meta = mock_collection.upsert.call_args[1]["metadatas"][0]
        assert meta["tags"] == "['a', 'b']"


# ------------------------------------------------------------------
# search_similar
# ------------------------------------------------------------------


class TestSearchSimilar:
    """Tests for VectorEngine.search_similar."""

    def test_search_empty_collection(self, engine, mock_collection):
        """Searching an empty collection returns an empty list."""
        mock_collection.count.return_value = 0
        results = engine.search_similar("sales", "widgets")
        assert results == []

    def test_search_returns_records(self, engine, mock_collection):
        """Matching results are converted to SimilarRecord objects."""
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "ids": [["r1", "r2"]],
            "distances": [[0.1, 0.3]],
            "metadatas": [[{"name": "A"}, {"name": "B"}]],
        }

        results = engine.search_similar("sales", "widgets", n_results=5)

        assert len(results) == 2
        assert isinstance(results[0], SimilarRecord)
        assert results[0].id == "r1"
        assert results[0].distance == pytest.approx(0.1)
        assert results[0].similarity == pytest.approx(0.9)
        assert results[1].record == {"name": "B"}

    def test_search_with_filters(self, engine, mock_collection):
        """Filters are forwarded as the 'where' clause."""
        mock_collection.count.return_value = 1
        mock_collection.query.return_value = {
            "ids": [["r1"]],
            "distances": [[0.05]],
            "metadatas": [[{"status": "active"}]],
        }

        engine.search_similar("sales", "widgets", filters={"status": "active"})

        call_kwargs = mock_collection.query.call_args[1]
        assert call_kwargs["where"] == {"status": "active"}


# ------------------------------------------------------------------
# search_by_example
# ------------------------------------------------------------------


class TestSearchByExample:
    """Tests for VectorEngine.search_by_example."""

    def test_search_by_example_not_found(self, engine, mock_collection):
        """Returns empty list when example record has no embedding."""
        mock_collection.get.return_value = {
            "embeddings": [None],
            "documents": [],
        }
        results = engine.search_by_example("sales", "missing")
        assert results == []

    def test_search_by_example_excludes_self(self, engine, mock_collection):
        """The example record itself is excluded from the results."""
        mock_collection.get.return_value = {
            "embeddings": [[0.1, 0.2]],
            "documents": ["doc"],
        }
        mock_collection.query.return_value = {
            "ids": [["r1", "r2", "r1"]],
            "distances": [[0.0, 0.2, 0.0]],
            "metadatas": [[{"a": 1}, {"b": 2}, {"a": 1}]],
        }

        results = engine.search_by_example("sales", "r1", n_results=5)

        returned_ids = [r.id for r in results]
        assert "r1" not in returned_ids
        assert "r2" in returned_ids

    def test_search_by_example_exception(self, engine, mock_collection):
        """Returns empty list when collection.get raises."""
        mock_collection.get.side_effect = Exception("fail")
        results = engine.search_by_example("sales", "bad_id")
        assert results == []


# ------------------------------------------------------------------
# find_patterns
# ------------------------------------------------------------------


class TestFindPatterns:
    """Tests for VectorEngine.find_patterns."""

    def test_find_patterns_numeric(self, engine, mock_collection):
        """Numeric fields produce min/max/avg ranges."""
        mock_collection.get.return_value = {
            "metadatas": [
                {"price": 10.0, "name": "A"},
                {"price": 20.0, "name": "B"},
            ],
        }
        result = engine.find_patterns("sales", ["1", "2"])

        assert isinstance(result, PatternResult)
        assert result.sample_count == 2
        assert "price" in result.numeric_ranges
        assert result.numeric_ranges["price"]["min"] == pytest.approx(10.0)
        assert result.numeric_ranges["price"]["max"] == pytest.approx(20.0)
        assert result.numeric_ranges["price"]["avg"] == pytest.approx(15.0)

    def test_find_patterns_categorical(self, engine, mock_collection):
        """Categorical fields produce frequency counts."""
        mock_collection.get.return_value = {
            "metadatas": [
                {"color": "red"},
                {"color": "red"},
                {"color": "blue"},
            ],
        }
        result = engine.find_patterns("sales", ["1", "2", "3"])

        assert "color" in result.frequent_values
        assert result.frequent_values["color"]["red"] == 2
        assert result.frequent_values["color"]["blue"] == 1

    def test_find_patterns_empty(self, engine, mock_collection):
        """Returns empty PatternResult when collection.get raises."""
        mock_collection.get.side_effect = Exception("fail")
        result = engine.find_patterns("sales", ["x"])

        assert result.sample_count == 0
        assert result.common_fields == {}

    def test_find_patterns_no_metadatas(self, engine, mock_collection):
        """Returns empty PatternResult when metadatas is empty."""
        mock_collection.get.return_value = {"metadatas": []}
        result = engine.find_patterns("sales", ["x"])
        assert result.sample_count == 0


# ------------------------------------------------------------------
# delete_collection
# ------------------------------------------------------------------


class TestDeleteCollection:
    """Tests for VectorEngine.delete_collection."""

    def test_delete_success(self, engine, mock_client):
        """Returns True when deletion succeeds."""
        assert engine.delete_collection("old_data") is True
        mock_client.delete_collection.assert_called_once_with(name="old_data")

    def test_delete_failure(self, engine, mock_client):
        """Returns False when deletion raises."""
        mock_client.delete_collection.side_effect = Exception("not found")
        assert engine.delete_collection("missing") is False


# ------------------------------------------------------------------
# list_collections
# ------------------------------------------------------------------


class TestListCollections:
    """Tests for VectorEngine.list_collections."""

    def test_list_collections(self, engine, mock_client):
        """Delegates to VectorClient and returns names."""
        result = engine.list_collections()
        assert result == ["sales", "products"]
        mock_client.list_collections.assert_called_once()


# ------------------------------------------------------------------
# get_collection_info
# ------------------------------------------------------------------


class TestGetCollectionInfo:
    """Tests for VectorEngine.get_collection_info."""

    def test_get_collection_info(self, engine, mock_collection):
        """Returns dict with name, count, and metadata."""
        mock_collection.count.return_value = 42
        info = engine.get_collection_info("sales")

        assert info["name"] == "sales"
        assert info["count"] == 42
        assert info["metadata"] == {"hnsw:space": "cosine"}

    def test_get_collection_info_error(self, engine, mock_client):
        """Returns zeroed info when collection access fails."""
        mock_client.get_or_create_collection.side_effect = Exception("fail")
        info = engine.get_collection_info("broken")

        assert info["count"] == 0
        assert info["metadata"] == {}
