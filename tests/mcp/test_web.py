"""Comprehensive tests for web scraping MCP tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.web import register


@pytest.fixture
def config() -> MCPConfig:
    """Create MCPConfig with defaults."""
    return MCPConfig()


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register web tools and return them by name."""
    mcp = MagicMock()
    registered: dict = {}

    def capture_tool():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mcp.tool.side_effect = capture_tool
    register(mcp, config)
    return registered


def _mock_async_client(mock_client: AsyncMock) -> patch:
    """Create a patch for httpx.AsyncClient context manager."""
    p = patch("httpx.AsyncClient")
    return p


# ---------------------------------------------------------------------------
# URL validation
# ---------------------------------------------------------------------------
class TestUrlValidation:
    """URL scheme validation tests."""

    @pytest.mark.asyncio
    async def test_invalid_url_no_scheme(self, tools: dict) -> None:
        result = await tools["scrape_url"]("example.com")
        assert "Error: Invalid URL" in result

    @pytest.mark.asyncio
    async def test_invalid_url_ftp(self, tools: dict) -> None:
        result = await tools["scrape_url"]("ftp://example.com")
        assert "Error: Invalid URL" in result

    @pytest.mark.asyncio
    async def test_invalid_url_empty(self, tools: dict) -> None:
        result = await tools["scrape_url"]("")
        assert "Error: Invalid URL" in result

    @pytest.mark.asyncio
    async def test_valid_http(self, tools: dict) -> None:
        """http:// is accepted (doesn't hit validation error)."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.text = "<html><body>OK</body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("http://example.com")

        assert "OK" in result


# ---------------------------------------------------------------------------
# Successful scraping
# ---------------------------------------------------------------------------
class TestSuccessfulScrape:
    """Successful scrape scenarios."""

    @pytest.mark.asyncio
    async def test_basic_html(self, tools: dict) -> None:
        html = "<html><body><p>Hello World</p></body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("https://example.com")

        assert "Hello World" in result

    @pytest.mark.asyncio
    async def test_script_tags_removed(self, tools: dict) -> None:
        html = (
            "<html><body><p>Content</p>"
            "<script>alert('xss')</script></body></html>"
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

        assert "Content" in result
        assert "alert" not in result

    @pytest.mark.asyncio
    async def test_style_tags_removed(self, tools: dict) -> None:
        html = (
            "<html><body><p>Content</p>"
            "<style>.red { color: red; }</style></body></html>"
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

        assert "Content" in result
        assert "color: red" not in result

    @pytest.mark.asyncio
    async def test_whitespace_collapsed(self, tools: dict) -> None:
        html = "<html><body><p>Hello    World     Here</p></body></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("https://example.com")

        assert "Hello World Here" in result

    @pytest.mark.asyncio
    async def test_html_without_body(self, tools: dict) -> None:
        """Handles HTML without a body tag (falls back to full tree)."""
        html = "<html><p>No body tag</p></html>"
        mock_response = MagicMock()
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("https://example.com")

        assert "No body tag" in result

    @pytest.mark.asyncio
    async def test_empty_lines_removed(self, tools: dict) -> None:
        html = (
            "<html><body>"
            "<p>Line1</p>"
            "<div></div><div></div>"
            "<p>Line2</p>"
            "</body></html>"
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

        # Empty lines should be filtered out
        lines = result.strip().splitlines()
        for line in lines:
            assert line.strip() != ""


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestErrorHandling:
    """Error conditions during scraping."""

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
    async def test_http_404(self, tools: dict) -> None:
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
        assert "404" in result

    @pytest.mark.asyncio
    async def test_http_500(self, tools: dict) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("https://example.com")

        assert "HTTP error" in result
        assert "500" in result

    @pytest.mark.asyncio
    async def test_unexpected_exception(self, tools: dict) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = RuntimeError("Unexpected")

        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value = mock_client
            mock_cls.return_value.__aexit__.return_value = None
            result = await tools["scrape_url"]("https://example.com")

        assert "Unexpected error" in result


# ---------------------------------------------------------------------------
# register function
# ---------------------------------------------------------------------------
class TestRegister:
    """Verify register adds expected tools."""

    def test_registers_one_tool(self, tools: dict) -> None:
        assert set(tools.keys()) == {"scrape_url"}
