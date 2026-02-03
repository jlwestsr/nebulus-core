"""Tests for the LLM client."""

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
