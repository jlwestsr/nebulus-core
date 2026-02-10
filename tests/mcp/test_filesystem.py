"""Comprehensive tests for filesystem MCP tools."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.filesystem import _validate_path, register


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
    """Register filesystem tools and return them by name."""
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
# _validate_path
# ---------------------------------------------------------------------------
class TestValidatePath:
    """Path validation and security checks."""

    def test_relative_path(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("subdir/file.txt", config)
        assert result == os.path.join(str(workspace), "subdir/file.txt")

    def test_dot_path(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path(".", config)
        assert result == os.path.join(str(workspace), ".")

    def test_leading_slash_stripped(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("/file.txt", config)
        assert result == os.path.join(str(workspace), "file.txt")

    def test_multiple_leading_slashes(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("///file.txt", config)
        assert result == os.path.join(str(workspace), "file.txt")

    def test_traversal_blocked(self, config: MCPConfig) -> None:
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("../../etc/passwd", config)

    def test_traversal_with_subdir_prefix(self, config: MCPConfig) -> None:
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("subdir/../../etc/passwd", config)

    def test_nested_path(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("a/b/c/d.txt", config)
        expected = os.path.join(str(workspace), "a/b/c/d.txt")
        assert result == expected

    def test_empty_string_path(self, config: MCPConfig, workspace: Path) -> None:
        """Empty string treated as workspace root."""
        result = _validate_path("", config)
        assert result == os.path.join(str(workspace), "")


# ---------------------------------------------------------------------------
# list_directory
# ---------------------------------------------------------------------------
class TestListDirectory:
    """list_directory tool tests."""

    def test_lists_files(self, tools: dict, workspace: Path) -> None:
        (workspace / "a.txt").write_text("a")
        (workspace / "b.txt").write_text("b")
        result = tools["list_directory"](".")
        assert "a.txt" in result
        assert "b.txt" in result

    def test_lists_subdirectories(self, tools: dict, workspace: Path) -> None:
        (workspace / "subdir").mkdir()
        result = tools["list_directory"](".")
        assert "subdir" in result

    def test_empty_directory(self, tools: dict, workspace: Path) -> None:
        (workspace / "empty").mkdir()
        result = tools["list_directory"]("empty")
        assert result == "(empty directory)"

    def test_default_path_is_dot(self, tools: dict, workspace: Path) -> None:
        (workspace / "file.txt").write_text("data")
        result = tools["list_directory"]()
        assert "file.txt" in result

    def test_nonexistent_directory(self, tools: dict) -> None:
        result = tools["list_directory"]("nonexistent")
        assert "Error" in result

    def test_traversal_error(self, tools: dict) -> None:
        result = tools["list_directory"]("../../etc")
        assert "Error" in result


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------
class TestReadFile:
    """read_file tool tests."""

    def test_read_existing_file(self, tools: dict, workspace: Path) -> None:
        (workspace / "hello.txt").write_text("hello world")
        result = tools["read_file"]("hello.txt")
        assert result == "hello world"

    def test_read_empty_file(self, tools: dict, workspace: Path) -> None:
        (workspace / "empty.txt").write_text("")
        result = tools["read_file"]("empty.txt")
        assert result == ""

    def test_read_multiline_file(self, tools: dict, workspace: Path) -> None:
        content = "line1\nline2\nline3"
        (workspace / "multi.txt").write_text(content)
        result = tools["read_file"]("multi.txt")
        assert result == content

    def test_read_utf8_content(self, tools: dict, workspace: Path) -> None:
        content = "Hello \u00e9\u00e8\u00ea \u00fc\u00f6\u00e4"
        (workspace / "utf8.txt").write_text(content, encoding="utf-8")
        result = tools["read_file"]("utf8.txt")
        assert result == content

    def test_read_missing_file(self, tools: dict) -> None:
        result = tools["read_file"]("missing.txt")
        assert "Error" in result

    def test_read_nested_file(self, tools: dict, workspace: Path) -> None:
        nested = workspace / "sub" / "dir"
        nested.mkdir(parents=True)
        (nested / "file.txt").write_text("nested content")
        result = tools["read_file"]("sub/dir/file.txt")
        assert result == "nested content"

    def test_read_traversal_blocked(self, tools: dict) -> None:
        result = tools["read_file"]("../../etc/passwd")
        assert "Error" in result


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------
class TestWriteFile:
    """write_file tool tests."""

    def test_write_new_file(self, tools: dict, workspace: Path) -> None:
        result = tools["write_file"]("new.txt", "content")
        assert "Successfully wrote" in result
        assert (workspace / "new.txt").read_text() == "content"

    def test_write_creates_parent_directories(
        self, tools: dict, workspace: Path
    ) -> None:
        result = tools["write_file"]("a/b/c/file.txt", "deep")
        assert "Successfully wrote" in result
        assert (workspace / "a" / "b" / "c" / "file.txt").read_text() == "deep"

    def test_write_overwrites_existing(self, tools: dict, workspace: Path) -> None:
        (workspace / "exist.txt").write_text("old")
        tools["write_file"]("exist.txt", "new")
        assert (workspace / "exist.txt").read_text() == "new"

    def test_write_empty_content(self, tools: dict, workspace: Path) -> None:
        result = tools["write_file"]("blank.txt", "")
        assert "Successfully wrote" in result
        assert (workspace / "blank.txt").read_text() == ""

    def test_write_utf8_content(self, tools: dict, workspace: Path) -> None:
        content = "Hello \u00e9\u00e8\u00ea \u00fc\u00f6\u00e4"
        tools["write_file"]("utf8.txt", content)
        assert (workspace / "utf8.txt").read_text(encoding="utf-8") == content

    def test_write_traversal_blocked(self, tools: dict) -> None:
        result = tools["write_file"]("../../outside.txt", "hack")
        assert "Error" in result


# ---------------------------------------------------------------------------
# edit_file
# ---------------------------------------------------------------------------
class TestEditFile:
    """edit_file tool tests."""

    def test_replaces_first_occurrence_only(
        self, tools: dict, workspace: Path
    ) -> None:
        (workspace / "edit.txt").write_text("foo bar foo baz")
        result = tools["edit_file"]("edit.txt", "foo", "qux")
        assert "Successfully edited" in result
        assert (workspace / "edit.txt").read_text() == "qux bar foo baz"

    def test_edit_full_word(self, tools: dict, workspace: Path) -> None:
        (workspace / "code.py").write_text("def hello():\n    return 42\n")
        tools["edit_file"]("code.py", "return 42", "return 99")
        assert (workspace / "code.py").read_text() == "def hello():\n    return 99\n"

    def test_edit_missing_file(self, tools: dict) -> None:
        result = tools["edit_file"]("missing.txt", "a", "b")
        assert "not found" in result

    def test_edit_target_not_found(self, tools: dict, workspace: Path) -> None:
        (workspace / "no_match.txt").write_text("hello world")
        result = tools["edit_file"]("no_match.txt", "MISSING", "replacement")
        assert "Target text missing" in result

    def test_edit_multiline_target(self, tools: dict, workspace: Path) -> None:
        content = "line1\nline2\nline3"
        (workspace / "multi.txt").write_text(content)
        result = tools["edit_file"]("multi.txt", "line1\nline2", "replaced")
        assert "Successfully edited" in result
        assert (workspace / "multi.txt").read_text() == "replaced\nline3"

    def test_edit_empty_replacement(self, tools: dict, workspace: Path) -> None:
        """Replacing with empty string effectively deletes."""
        (workspace / "del.txt").write_text("keep remove keep")
        tools["edit_file"]("del.txt", " remove", "")
        assert (workspace / "del.txt").read_text() == "keep keep"

    def test_edit_traversal_blocked(self, tools: dict) -> None:
        result = tools["edit_file"]("../../etc/passwd", "root", "hack")
        assert "Error" in result


# ---------------------------------------------------------------------------
# register function
# ---------------------------------------------------------------------------
class TestRegister:
    """Verify register adds all expected tools."""

    def test_registers_four_tools(self, tools: dict) -> None:
        expected = {"list_directory", "read_file", "write_file", "edit_file"}
        assert set(tools.keys()) == expected

    def test_tool_called_registers_decorator(self, config: MCPConfig) -> None:
        """mcp.tool() is called once per tool."""
        mcp = MagicMock()
        call_count = 0

        def capture_tool():
            nonlocal call_count
            call_count += 1

            def decorator(func):
                return func

            return decorator

        mcp.tool.side_effect = capture_tool
        register(mcp, config)
        assert call_count == 4
