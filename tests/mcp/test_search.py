"""Comprehensive tests for search MCP tools."""

import os
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
    """Create a temporary workspace directory."""
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> MCPConfig:
    """Create MCPConfig pointing to the temp workspace."""
    return MCPConfig(workspace_path=workspace)


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register search tools and return them by name."""
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


# ---------------------------------------------------------------------------
# _search_ddg
# ---------------------------------------------------------------------------
class TestSearchDDG:
    """DuckDuckGo search helper tests."""

    @patch("duckduckgo_search.DDGS")
    def test_returns_formatted(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "href": "https://example.com", "body": "Snippet 1"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs

        results = _search_ddg("test query", 5)
        assert len(results) == 1
        assert "Result 1" in results[0]
        assert "https://example.com" in results[0]
        assert "Snippet 1" in results[0]

    @patch("duckduckgo_search.DDGS")
    def test_multiple_results(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = [
            {"title": "A", "href": "https://a.com", "body": "a"},
            {"title": "B", "href": "https://b.com", "body": "b"},
            {"title": "C", "href": "https://c.com", "body": "c"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs

        results = _search_ddg("query", 3)
        assert len(results) == 3

    @patch("duckduckgo_search.DDGS")
    def test_empty_results(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs

        results = _search_ddg("obscure query", 5)
        assert results == []

    @patch("duckduckgo_search.DDGS")
    def test_passes_max_results(self, mock_ddgs_cls: MagicMock) -> None:
        mock_ddgs = MagicMock()
        mock_ddgs.text.return_value = []
        mock_ddgs_cls.return_value = mock_ddgs

        _search_ddg("test", 10)
        mock_ddgs.text.assert_called_once_with("test", max_results=10)


# ---------------------------------------------------------------------------
# _search_google_api
# ---------------------------------------------------------------------------
class TestSearchGoogleAPI:
    """Google Custom Search API helper tests."""

    def test_missing_credentials_raises(self) -> None:
        config = MCPConfig()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                _search_google_api("test", 5, config)

    def test_missing_only_api_key_raises(self) -> None:
        config = MCPConfig(google_cse_id="cse")
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                _search_google_api("test", 5, config)

    def test_missing_only_cse_id_raises(self) -> None:
        config = MCPConfig(google_api_key="key")
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                _search_google_api("test", 5, config)

    @patch("googleapiclient.discovery.build")
    def test_with_config_credentials(self, mock_build: MagicMock) -> None:
        config = MCPConfig(google_api_key="key", google_cse_id="cse")
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse().list().execute.return_value = {
            "items": [
                {"title": "T", "link": "L", "snippet": "S"},
            ]
        }
        results = _search_google_api("test", 5, config)
        assert len(results) == 1
        assert "Title: T" in results[0]
        assert "Link: L" in results[0]
        assert "Snippet: S" in results[0]

    @patch("googleapiclient.discovery.build")
    def test_with_env_credentials(self, mock_build: MagicMock) -> None:
        config = MCPConfig()
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse().list().execute.return_value = {
            "items": [{"title": "E", "link": "EL", "snippet": "ES"}]
        }
        with patch.dict(
            os.environ, {"GOOGLE_API_KEY": "env-key", "GOOGLE_CSE_ID": "env-cse"}
        ):
            results = _search_google_api("test", 5, config)
        assert len(results) == 1

    @patch("googleapiclient.discovery.build")
    def test_empty_items(self, mock_build: MagicMock) -> None:
        config = MCPConfig(google_api_key="k", google_cse_id="c")
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse().list().execute.return_value = {"items": []}
        results = _search_google_api("test", 5, config)
        assert results == []

    @patch("googleapiclient.discovery.build")
    def test_no_items_key(self, mock_build: MagicMock) -> None:
        config = MCPConfig(google_api_key="k", google_cse_id="c")
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_service.cse().list().execute.return_value = {}
        results = _search_google_api("test", 5, config)
        assert results == []


# ---------------------------------------------------------------------------
# _search_google_fallback
# ---------------------------------------------------------------------------
class TestSearchGoogleFallback:
    """Google fallback scraper tests."""

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
        assert "https://example.com" in results[0]

    @patch("googlesearch.search", side_effect=Exception("Network error"))
    def test_returns_empty_on_exception(self, mock_search: MagicMock) -> None:
        results = _search_google_fallback("test", 5)
        assert results == []

    @patch("googlesearch.search", side_effect=ImportError("not installed"))
    def test_returns_empty_on_import_error(self, mock_search: MagicMock) -> None:
        results = _search_google_fallback("test", 5)
        assert results == []

    @patch("googlesearch.search")
    def test_multiple_results(self, mock_search: MagicMock) -> None:
        r1 = MagicMock(title="A", url="https://a.com", description="a")
        r2 = MagicMock(title="B", url="https://b.com", description="b")
        mock_search.return_value = [r1, r2]

        results = _search_google_fallback("test", 2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# search_web tool
# ---------------------------------------------------------------------------
class TestSearchWebTool:
    """search_web tool tests."""

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    def test_default_engine_is_ddg(self, mock_ddg: MagicMock, tools: dict) -> None:
        mock_ddg.return_value = ["Title: T\nLink: L\nSnippet: S\n"]
        result = tools["search_web"]("query")
        assert "Title: T" in result
        mock_ddg.assert_called_once_with("query", 5)

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    def test_custom_max_results(self, mock_ddg: MagicMock, tools: dict) -> None:
        mock_ddg.return_value = ["Title: T\nLink: L\nSnippet: S\n"]
        tools["search_web"]("query", max_results=10)
        mock_ddg.assert_called_once_with("query", 10)

    @patch("nebulus_core.mcp.tools.search._search_google_api")
    def test_google_engine(self, mock_google: MagicMock, tools: dict) -> None:
        mock_google.return_value = ["Title: G\nLink: GL\nSnippet: GS\n"]
        result = tools["search_web"]("query", engine="google")
        assert "Title: G" in result

    @patch("nebulus_core.mcp.tools.search._search_google_api")
    def test_google_engine_case_insensitive(
        self, mock_google: MagicMock, tools: dict
    ) -> None:
        mock_google.return_value = ["Title: G\nLink: GL\nSnippet: GS\n"]
        result = tools["search_web"]("query", engine="Google")
        assert "Title: G" in result

    @patch("nebulus_core.mcp.tools.search._search_google_api")
    def test_google_value_error_returns_message(
        self, mock_google: MagicMock, tools: dict
    ) -> None:
        mock_google.side_effect = ValueError("Missing credentials")
        result = tools["search_web"]("query", engine="google")
        assert "Missing credentials" in result

    @patch("nebulus_core.mcp.tools.search._search_google_api")
    def test_google_import_error_returns_message(
        self, mock_google: MagicMock, tools: dict
    ) -> None:
        mock_google.side_effect = ImportError("not installed")
        result = tools["search_web"]("query", engine="google")
        assert "not installed" in result

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    @patch("nebulus_core.mcp.tools.search._search_google_fallback")
    def test_fallback_when_ddg_empty(
        self, mock_fallback: MagicMock, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.return_value = []
        mock_fallback.return_value = ["Title: F\nLink: FL\nSnippet: FS\n"]
        result = tools["search_web"]("query")
        assert "Title: F" in result

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    @patch("nebulus_core.mcp.tools.search._search_google_fallback")
    def test_no_results_anywhere(
        self, mock_fallback: MagicMock, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.return_value = []
        mock_fallback.return_value = []
        result = tools["search_web"]("query")
        assert result == "No results found."

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    def test_multiple_results_joined_by_separator(
        self, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.return_value = ["Result1\n", "Result2\n"]
        result = tools["search_web"]("query")
        assert "---" in result

    @patch("nebulus_core.mcp.tools.search._search_ddg")
    def test_exception_returns_error(
        self, mock_ddg: MagicMock, tools: dict
    ) -> None:
        mock_ddg.side_effect = RuntimeError("Connection failed")
        result = tools["search_web"]("query")
        assert "Error performing search" in result


# ---------------------------------------------------------------------------
# search_code tool
# ---------------------------------------------------------------------------
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

        result = tools["search_code"]("nothing_here")
        assert result == "No matches found."

    @patch("subprocess.run")
    def test_grep_error(self, mock_run: MagicMock, tools: dict) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stderr = "grep: invalid regex"
        mock_run.return_value = mock_result

        result = tools["search_code"]("[invalid")
        assert "Error executing grep" in result
        assert "exit 2" in result

    @patch("subprocess.run")
    def test_timeout(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(["grep"], 30)
        result = tools["search_code"]("query")
        assert "timed out" in result

    @patch("subprocess.run")
    def test_custom_path(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        (workspace / "sub").mkdir()
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "sub/file.py:1:match"
        mock_run.return_value = mock_result

        result = tools["search_code"]("match", path="sub")
        assert result == "sub/file.py:1:match"

    @patch("subprocess.run")
    def test_grep_called_with_correct_args(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        tools["search_code"]("pattern")

        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "grep"
        assert "-r" in cmd
        assert "-n" in cmd
        assert "-I" in cmd
        assert "-H" in cmd
        assert "pattern" in cmd
        assert call_args[1]["cwd"] == str(workspace)

    def test_path_traversal_blocked(self, tools: dict) -> None:
        result = tools["search_code"]("query", path="../../etc")
        assert "Error" in result

    @patch("subprocess.run")
    def test_generic_exception(
        self, mock_run: MagicMock, tools: dict
    ) -> None:
        mock_run.side_effect = OSError("Permission denied")
        result = tools["search_code"]("query")
        assert "Error executing search" in result


# ---------------------------------------------------------------------------
# register function
# ---------------------------------------------------------------------------
class TestRegister:
    """Verify register adds expected tools."""

    def test_registers_two_tools(self, tools: dict) -> None:
        expected = {"search_web", "search_code"}
        assert set(tools.keys()) == expected
