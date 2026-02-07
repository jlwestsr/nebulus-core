"""Tests for the LLM client."""

import httpx
import pytest

from nebulus_core.llm.client import LLMClient


class TestLLMClient:
    """Tests for the OpenAI-compatible HTTP client."""

    def test_base_url_trailing_slash_stripped(self) -> None:
        """Trailing slash on base_url should be normalized."""
        client = LLMClient(base_url="http://localhost:5000/v1/")
        assert client.base_url == "http://localhost:5000/v1"

    def test_health_check_returns_false_on_connect_error(self) -> None:
        """Health check should return False when server is unreachable."""
        client = LLMClient(base_url="http://localhost:99999/v1", timeout=1.0)
        assert client.health_check() is False

    def test_context_manager(self) -> None:
        """Client should support context manager protocol."""
        with LLMClient(base_url="http://localhost:5000/v1") as client:
            assert client.base_url == "http://localhost:5000/v1"


class TestLLMClientValidation:
    """Tests for base_url validation on construction."""

    def test_empty_base_url_raises(self) -> None:
        """Empty base_url should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty base_url"):
            LLMClient(base_url="")

    def test_whitespace_base_url_raises(self) -> None:
        """Whitespace-only base_url should raise ValueError."""
        with pytest.raises(ValueError, match="non-empty base_url"):
            LLMClient(base_url="   ")

    def test_invalid_scheme_raises(self) -> None:
        """base_url without http/https scheme should raise ValueError."""
        with pytest.raises(ValueError, match="http:// or https://"):
            LLMClient(base_url="ftp://localhost:5000/v1")

    def test_no_scheme_raises(self) -> None:
        """base_url without any scheme should raise ValueError."""
        with pytest.raises(ValueError, match="http:// or https://"):
            LLMClient(base_url="localhost:5000/v1")

    def test_https_url_accepted(self) -> None:
        """https:// URLs should be accepted."""
        client = LLMClient(base_url="https://api.example.com/v1")
        assert client.base_url == "https://api.example.com/v1"


class TestLLMClientDegradation:
    """Tests for graceful degradation when server is unreachable."""

    def test_chat_raises_on_unreachable_server(self) -> None:
        """chat() should raise httpx.ConnectError for unreachable server."""
        client = LLMClient(base_url="http://localhost:99999/v1", timeout=1.0)
        with pytest.raises(httpx.ConnectError):
            client.chat(messages=[{"role": "user", "content": "hello"}])
