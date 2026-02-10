"""Tests for search MCP tools."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.search import (
    _search_ddg,
    _search_google_api,
    _search_google_fallback,
    register,
)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> MCPConfig:
    return MCPConfig(workspace_path=workspace)


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register search tools and return them by name."""
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


class TestSearchDDG:
    """DuckDuckGo search helper tests."""

    @patch("duckduckgo_search.DDGS")
    def test_returns_formatted_results(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "href": "https://example.com", "body": "Snippet 1"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs

        results = _search_ddg("test query", 5)
        assert len(results) == 1
        assert "Result 1" in results[0]
        assert "https://example.com" in results[0]


class TestSearchGoogleAPI:
    """Google API search helper tests."""

    def test_missing_credentials(self) -> None:
        config = MCPConfig()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                _search_google_api("test", 5, config)

    def test_with_config_credentials(self) -> None:
        config = MCPConfig(google_api_key="key", google_cse_id="cse")
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_service = MagicMock()
            mock_build.return_value = mock_service
            mock_service.cse().list().execute.return_value = {
                "items": [
                    {"title": "T", "link": "L", "snippet": "S"},
                ]
            }
            results = _search_google_api("test", 5, config)
            assert len(results) == 1


class TestSearchGoogleFallback:
    """Google fallback search tests."""

    @patch("googlesearch.search")
    def test_returns_formatted(self, mock_search: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.title = "Title"
        mock_result.url = "https://example.com"
        mock_result.description = "Desc"
        mock_search.return_value = [mock_result]

        results = _search_google_fallback("test", 5)
        assert len(results) == 1
        assert "Title" in results[0]

    @patch("googlesearch.search", side_effect=Exception("fail"))
    def test_returns_empty_on_error(self, mock_search: MagicMock) -> None:
        results = _search_google_fallback("test", 5)
        assert results == []


class TestSearchWebTool:
    """search_web tool tests."""

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    def test_ddg_default(self, mock_ddg: MagicMock, tools: dict) -> None:
        mock_ddg.return_value = ["Title: T\nLink: L\nSnippet: S\n"]
        result = tools["search_web"]("query")
        assert "Title: T" in result
        mock_ddg.assert_called_once_with("query", 5)

    @patch("nebulus_core.mcp.tools.search._search_google_api")
    def test_google_engine(self, mock_google: MagicMock, tools: dict) -> None:
        mock_google.return_value = ["Title: G\nLink: GL\nSnippet: GS\n"]
        result = tools["search_web"]("query", engine="google")
        assert "Title: G" in result

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    @patch("nebulus_core.mcp.tools.search._search_google_fallback")
    def test_fallback_when_empty(
        self, mock_fallback: MagicMock, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.return_value = []
        mock_fallback.return_value = ["Title: F\nLink: FL\nSnippet: FS\n"]
        result = tools["search_web"]("query")
        assert "Title: F" in result

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    @patch("nebulus_core.mcp.tools.search._search_google_fallback")
    def test_no_results(
        self, mock_fallback: MagicMock, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.return_value = []
        mock_fallback.return_value = []
        result = tools["search_web"]("query")
        assert result == "No results found."


class TestSearchCodeTool:
    """search_code tool tests."""

    @patch("subprocess.run")
    def test_successful_search(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "file.py:10:def foo():"
        mock_run.return_value = mock_result

        result = tools["search_code"]("def foo")
        assert result == "file.py:10:def foo():"

    @patch("subprocess.run")
    def test_no_matches(self, mock_run: MagicMock, tools: dict) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = tools["search_code"]("missing")
        assert result == "No matches found."

    @patch("subprocess.run")
    def test_grep_error(self, mock_run: MagicMock, tools: dict) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stderr = "grep error"
        mock_run.return_value = mock_result

        result = tools["search_code"]("bad")
        assert "Error executing grep" in result

    @patch("subprocess.run")
    def test_timeout(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(["grep"], 30)
        result = tools["search_code"]("query")
        assert "timed out" in result
