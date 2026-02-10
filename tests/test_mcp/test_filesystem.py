"""Tests for filesystem MCP tools."""

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
    registered = {}

    def capture_tool():
        def decorator(func):
            registered[func.__name__] = func
            return func

        return decorator

    mcp.tool.side_effect = capture_tool
    register(mcp, config)
    return registered


class TestValidatePath:
    """Path validation tests."""

    def test_valid_relative_path(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("subdir/file.txt", config)
        assert result == os.path.join(str(workspace), "subdir/file.txt")

    def test_valid_root_path(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path(".", config)
        assert result == os.path.join(str(workspace), ".")

    def test_traversal_blocked(self, config: MCPConfig) -> None:
        with pytest.raises(ValueError, match="Access denied"):
            _validate_path("../../etc/passwd", config)

    def test_leading_slash_stripped(self, config: MCPConfig, workspace: Path) -> None:
        result = _validate_path("/file.txt", config)
        assert result == os.path.join(str(workspace), "file.txt")


class TestListDirectory:
    """list_directory tool tests."""

    def test_list_files(self, tools: dict, workspace: Path) -> None:
        (workspace / "file1.txt").write_text("hello")
        (workspace / "file2.txt").write_text("world")
        result = tools["list_directory"](".")
        assert "file1.txt" in result
        assert "file2.txt" in result

    def test_empty_directory(self, tools: dict, workspace: Path) -> None:
        subdir = workspace / "empty"
        subdir.mkdir()
        result = tools["list_directory"]("empty")
        assert result == "(empty directory)"

    def test_nonexistent_directory(self, tools: dict) -> None:
        result = tools["list_directory"]("nonexistent")
        assert "Error" in result


class TestReadFile:
    """read_file tool tests."""

    def test_read_existing(self, tools: dict, workspace: Path) -> None:
        (workspace / "test.txt").write_text("hello world")
        result = tools["read_file"]("test.txt")
        assert result == "hello world"

    def test_read_missing(self, tools: dict) -> None:
        result = tools["read_file"]("missing.txt")
        assert "Error" in result


class TestWriteFile:
    """write_file tool tests."""

    def test_write_new(self, tools: dict, workspace: Path) -> None:
        result = tools["write_file"]("new.txt", "content")
        assert "Successfully wrote" in result
        assert (workspace / "new.txt").read_text() == "content"

    def test_write_creates_parent_dirs(self, tools: dict, workspace: Path) -> None:
        result = tools["write_file"]("deep/nested/file.txt", "data")
        assert "Successfully wrote" in result
        assert (workspace / "deep" / "nested" / "file.txt").read_text() == "data"

    def test_write_overwrites(self, tools: dict, workspace: Path) -> None:
        (workspace / "existing.txt").write_text("old")
        tools["write_file"]("existing.txt", "new")
        assert (workspace / "existing.txt").read_text() == "new"


class TestEditFile:
    """edit_file tool tests."""

    def test_edit_replaces_first(self, tools: dict, workspace: Path) -> None:
        (workspace / "edit.txt").write_text("Hello World World")
        result = tools["edit_file"]("edit.txt", "World", "Nebulus")
        assert "Successfully edited" in result
        assert (workspace / "edit.txt").read_text() == "Hello Nebulus World"

    def test_edit_missing_file(self, tools: dict) -> None:
        result = tools["edit_file"]("missing.txt", "a", "b")
        assert "not found" in result

    def test_edit_missing_text(self, tools: dict, workspace: Path) -> None:
        (workspace / "edit2.txt").write_text("Hello")
        result = tools["edit_file"]("edit2.txt", "MISSING", "replacement")
        assert "Target text missing" in result
