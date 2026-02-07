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
