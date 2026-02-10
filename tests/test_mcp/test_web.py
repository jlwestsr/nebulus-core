"""Tests for web scraping MCP tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.web import register


@pytest.fixture
def config() -> MCPConfig:
    return MCPConfig()


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register web tools and return them by name."""
    mcp = MagicMock()
    registered = {}

    def capture_tool():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mcp.tool.side_effect = capture_tool
    register(mcp, config)
    return registered


class TestScrapeUrl:
    """scrape_url tool tests."""

    @pytest.mark.asyncio
    async def test_invalid_url(self, tools: dict) -> None:
        result = await tools["scrape_url"]("not-a-url")
        assert "Error: Invalid URL" in result

    @pytest.mark.asyncio
    async def test_successful_scrape(self, tools: dict) -> None:
        html = (
            "<html><body><h1>Title</h1><p>Content  with  spaces</p>"
            "<script>var x=1;</script></body></html>"
        )
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None

            result = await tools["scrape_url"]("https://example.com")

        assert "Title" in result
        assert "Content with spaces" in result
        assert "var x=1" not in result

    @pytest.mark.asyncio
    async def test_request_error(self, tools: dict) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("Connection refused")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None

            result = await tools["scrape_url"]("https://example.com")

        assert "Error scraping URL" in result

    @pytest.mark.asyncio
    async def test_http_status_error(self, tools: dict) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None

            result = await tools["scrape_url"]("https://example.com")

        assert "HTTP error" in result
