"""Tests for VectorClient validation and graceful degradation."""

from unittest.mock import patch, MagicMock

import pytest

from nebulus_core.vector.client import VectorClient


class TestVectorClientValidation:
    """Tests for settings validation on construction."""

    def test_http_mode_missing_host_raises(self) -> None:
        """HTTP mode without 'host' should raise ValueError."""
        with pytest.raises(ValueError, match="'host' and 'port'"):
            VectorClient(settings={"mode": "http", "port": 8001})

    def test_http_mode_missing_port_raises(self) -> None:
        """HTTP mode without 'port' should raise ValueError."""
        with pytest.raises(ValueError, match="'host' and 'port'"):
            VectorClient(settings={"mode": "http", "host": "localhost"})

    def test_http_mode_missing_both_raises(self) -> None:
        """HTTP mode without host or port should raise ValueError."""
        with pytest.raises(ValueError, match="'host' and 'port'"):
            VectorClient(settings={"mode": "http"})

    def test_embedded_mode_missing_path_raises(self) -> None:
        """Embedded mode without 'path' should raise ValueError."""
        with pytest.raises(ValueError, match="'path'"):
            VectorClient(settings={"mode": "embedded"})

    def test_unknown_mode_raises(self) -> None:
        """Unknown mode should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown VectorClient mode"):
            VectorClient(settings={"mode": "grpc"})

    def test_default_mode_is_http(self) -> None:
        """Settings without 'mode' should default to http and validate."""
        with pytest.raises(ValueError, match="'host' and 'port'"):
            VectorClient(settings={})


class TestVectorClientHeartbeat:
    """Tests for heartbeat graceful degradation."""

    def test_heartbeat_returns_false_on_connection_failure(self) -> None:
        """heartbeat() should return False when ChromaDB is unreachable."""
        mock_chroma = MagicMock()
        mock_chroma.heartbeat.side_effect = Exception("Connection refused")

        with patch("nebulus_core.vector.client.chromadb") as mock_mod:
            mock_mod.HttpClient.return_value = mock_chroma
            client = VectorClient(
                settings={"mode": "http", "host": "localhost", "port": 19999}
            )

        assert client.heartbeat() is False

    def test_heartbeat_returns_true_on_success(self) -> None:
        """heartbeat() should return True when ChromaDB responds."""
        mock_chroma = MagicMock()
        mock_chroma.heartbeat.return_value = 1234567890

        with patch("nebulus_core.vector.client.chromadb") as mock_mod:
            mock_mod.HttpClient.return_value = mock_chroma
            client = VectorClient(
                settings={"mode": "http", "host": "localhost", "port": 8001}
            )

        assert client.heartbeat() is True


class TestVectorClientAddDocuments:
    """Tests for add_documents convenience method."""

    def _make_client(self) -> tuple[VectorClient, MagicMock]:
        mock_chroma = MagicMock()
        with patch("nebulus_core.vector.client.chromadb") as mock_mod:
            mock_mod.HttpClient.return_value = mock_chroma
            client = VectorClient(
                settings={"mode": "http", "host": "localhost", "port": 8001}
            )
        return client, mock_chroma

    def test_add_documents_creates_collection_and_adds(self) -> None:
        """add_documents should get_or_create collection then call add."""
        client, mock_chroma = self._make_client()
        mock_collection = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection

        client.add_documents(
            "test_col", ids=["1", "2"], documents=["doc1", "doc2"]
        )

        mock_chroma.get_or_create_collection.assert_called_once_with(name="test_col")
        mock_collection.add.assert_called_once_with(
            ids=["1", "2"], documents=["doc1", "doc2"], metadatas=[{}, {}]
        )

    def test_add_documents_passes_metadatas(self) -> None:
        """add_documents should forward explicit metadatas."""
        client, mock_chroma = self._make_client()
        mock_collection = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection

        metas = [{"k": "v1"}, {"k": "v2"}]
        client.add_documents(
            "col", ids=["1", "2"], documents=["a", "b"], metadatas=metas
        )

        mock_collection.add.assert_called_once_with(
            ids=["1", "2"], documents=["a", "b"], metadatas=metas
        )


class TestVectorClientSearch:
    """Tests for search convenience method."""

    def _make_client(self) -> tuple[VectorClient, MagicMock]:
        mock_chroma = MagicMock()
        with patch("nebulus_core.vector.client.chromadb") as mock_mod:
            mock_mod.HttpClient.return_value = mock_chroma
            client = VectorClient(
                settings={"mode": "http", "host": "localhost", "port": 8001}
            )
        return client, mock_chroma

    def test_search_basic(self) -> None:
        """search should query the collection and return results."""
        client, mock_chroma = self._make_client()
        mock_collection = MagicMock()
        expected = {"ids": [["1"]], "documents": [["doc1"]], "distances": [[0.1]]}
        mock_collection.query.return_value = expected
        mock_chroma.get_or_create_collection.return_value = mock_collection

        result = client.search("col", "hello", n_results=3)

        mock_collection.query.assert_called_once_with(
            query_texts=["hello"], n_results=3
        )
        assert result == expected

    def test_search_with_where_filter(self) -> None:
        """search should pass where filter when provided."""
        client, mock_chroma = self._make_client()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}
        mock_chroma.get_or_create_collection.return_value = mock_collection

        where = {"category": "docs"}
        client.search("col", "query", where=where)

        mock_collection.query.assert_called_once_with(
            query_texts=["query"], n_results=5, where=where
        )

    def test_search_without_where_omits_key(self) -> None:
        """search without where should not pass where kwarg."""
        client, mock_chroma = self._make_client()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {"ids": [[]], "documents": [[]]}
        mock_chroma.get_or_create_collection.return_value = mock_collection

        client.search("col", "query")

        mock_collection.query.assert_called_once_with(
            query_texts=["query"], n_results=5
        )


class TestVectorClientDeleteDocuments:
    """Tests for delete_documents convenience method."""

    def test_delete_documents(self) -> None:
        """delete_documents should get collection and call delete."""
        mock_chroma = MagicMock()
        with patch("nebulus_core.vector.client.chromadb") as mock_mod:
            mock_mod.HttpClient.return_value = mock_chroma
            client = VectorClient(
                settings={"mode": "http", "host": "localhost", "port": 8001}
            )

        mock_collection = MagicMock()
        mock_chroma.get_or_create_collection.return_value = mock_collection

        client.delete_documents("col", ids=["a", "b"])

        mock_chroma.get_or_create_collection.assert_called_once_with(name="col")
        mock_collection.delete.assert_called_once_with(ids=["a", "b"])
