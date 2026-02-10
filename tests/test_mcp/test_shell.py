"""Tests for shell execution MCP tool."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.shell import register


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def config(workspace: Path) -> MCPConfig:
    return MCPConfig(workspace_path=workspace)


@pytest.fixture
def tools(config: MCPConfig) -> dict:
    """Register shell tools and return them by name."""
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


class TestRunCommand:
    """run_command tool tests."""

    @patch("subprocess.run")
    def test_allowed_command(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_run.return_value = mock_result

        result = tools["run_command"]("ls -la")
        assert result == "output"
        mock_run.assert_called_with(
            ["ls", "-la"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_blocked_binary(self, tools: dict) -> None:
        result = tools["run_command"]("rm file.txt")
        assert "Error: Command" in result
        assert "not allowed" in result

    def test_blocked_operator_semicolon(self, tools: dict) -> None:
        result = tools["run_command"]("ls; rm file")
        assert "Error: Operator" in result
        assert "not allowed" in result

    def test_blocked_operator_pipe(self, tools: dict) -> None:
        result = tools["run_command"]("ls | grep foo")
        assert "Error: Operator" in result

    def test_blocked_operator_redirect(self, tools: dict) -> None:
        result = tools["run_command"]("echo hi > file.txt")
        assert "Error: Operator" in result

    def test_blocked_operator_backtick(self, tools: dict) -> None:
        result = tools["run_command"]("echo `whoami`")
        assert "Error: Operator" in result

    def test_blocked_operator_subshell(self, tools: dict) -> None:
        result = tools["run_command"]("echo $(whoami)")
        assert "Error: Operator" in result

    @patch("subprocess.run")
    def test_command_failure(self, mock_run: MagicMock, tools: dict) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error output"
        mock_run.return_value = mock_result

        result = tools["run_command"]("ls nonexistent")
        assert "Command failed" in result

    @patch("subprocess.run")
    def test_timeout(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(["echo"], 30)
        result = tools["run_command"]("echo test")
        assert "timed out" in result

    def test_empty_command(self, tools: dict) -> None:
        result = tools["run_command"]("")
        # shlex.split("") returns [], so "Empty command" or an error
        assert "Error" in result

    def test_custom_allowed_commands(self, workspace: Path) -> None:
        """Test that custom allowed_commands config is respected."""
        config = MCPConfig(
            workspace_path=workspace,
            allowed_commands={"echo"},
        )
        mcp = MagicMock()
        registered = {}

        def capture_tool():
            def decorator(func):
                registered[func.__name__] = func
                return func

            return decorator

        mcp.tool.side_effect = capture_tool
        register(mcp, config)

        # ls should be blocked with custom config
        result = registered["run_command"]("ls")
        assert "not allowed" in result
