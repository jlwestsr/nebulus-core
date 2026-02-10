"""Comprehensive tests for shell execution MCP tool."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools.shell import register


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
    """Register shell tools and return them by name."""
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
# Security — blocked operators
# ---------------------------------------------------------------------------
class TestBlockedOperators:
    """All blocked operators are rejected."""

    def test_pipe(self, tools: dict) -> None:
        result = tools["run_command"]("ls | grep foo")
        assert "Error: Operator" in result
        assert "not allowed" in result

    def test_semicolon(self, tools: dict) -> None:
        result = tools["run_command"]("ls; rm -rf /")
        assert "Error: Operator" in result

    def test_redirect_out(self, tools: dict) -> None:
        result = tools["run_command"]("echo hi > file.txt")
        assert "Error: Operator" in result

    def test_redirect_append(self, tools: dict) -> None:
        result = tools["run_command"]("echo hi >> file.txt")
        assert "Error: Operator" in result

    def test_ampersand(self, tools: dict) -> None:
        result = tools["run_command"]("ls &")
        assert "Error: Operator" in result

    def test_backtick(self, tools: dict) -> None:
        result = tools["run_command"]("echo `whoami`")
        assert "Error: Operator" in result

    def test_subshell(self, tools: dict) -> None:
        result = tools["run_command"]("echo $(whoami)")
        assert "Error: Operator" in result


# ---------------------------------------------------------------------------
# Security — command whitelist
# ---------------------------------------------------------------------------
class TestCommandWhitelist:
    """Only whitelisted commands are permitted."""

    def test_disallowed_command(self, tools: dict) -> None:
        result = tools["run_command"]("rm file.txt")
        assert "Error: Command" in result
        assert "not allowed" in result

    def test_disallowed_curl(self, tools: dict) -> None:
        result = tools["run_command"]("curl https://example.com")
        assert "not allowed" in result

    def test_disallowed_python(self, tools: dict) -> None:
        result = tools["run_command"]("python -c 'print(1)'")
        assert "not allowed" in result

    @patch("subprocess.run")
    def test_allowed_ls(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="file.txt\n")
        result = tools["run_command"]("ls")
        assert result == "file.txt\n"

    @patch("subprocess.run")
    def test_allowed_echo(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="hello\n")
        result = tools["run_command"]("echo hello")
        assert result == "hello\n"

    @patch("subprocess.run")
    def test_allowed_git(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="main\n")
        result = tools["run_command"]("git branch")
        assert result == "main\n"

    @patch("subprocess.run")
    def test_allowed_pytest(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="passed\n")
        result = tools["run_command"]("pytest tests/")
        assert result == "passed\n"

    def test_custom_allowed_commands(self, workspace: Path) -> None:
        """Custom allowed set restricts to only those commands."""
        config = MCPConfig(
            workspace_path=workspace,
            allowed_commands={"echo"},
        )
        mcp = MagicMock()
        registered: dict = {}

        def capture_tool():
            def decorator(func):
                registered[func.__name__] = func
                return func

            return decorator

        mcp.tool.side_effect = capture_tool
        register(mcp, config)

        # ls should now be blocked
        result = registered["run_command"]("ls")
        assert "not allowed" in result


# ---------------------------------------------------------------------------
# Successful execution
# ---------------------------------------------------------------------------
class TestSuccessfulExecution:
    """Commands that run successfully."""

    @patch("subprocess.run")
    def test_returns_stdout(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="output here")
        result = tools["run_command"]("ls -la")
        assert result == "output here"

    @patch("subprocess.run")
    def test_subprocess_called_correctly(
        self, mock_run: MagicMock, tools: dict, workspace: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        tools["run_command"]("ls -la")
        mock_run.assert_called_once_with(
            ["ls", "-la"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=30,
        )

    @patch("subprocess.run")
    def test_quoted_arguments(
        self, mock_run: MagicMock, tools: dict
    ) -> None:
        """shlex handles quoted args properly."""
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        tools["run_command"]('grep "hello world" file.txt')
        call_args = mock_run.call_args[0][0]
        assert call_args == ["grep", "hello world", "file.txt"]

    @patch("subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock, workspace: Path) -> None:
        """Custom command_timeout is passed to subprocess."""
        config = MCPConfig(workspace_path=workspace, command_timeout=120)
        mcp = MagicMock()
        registered: dict = {}

        def capture_tool():
            def decorator(func):
                registered[func.__name__] = func
                return func

            return decorator

        mcp.tool.side_effect = capture_tool
        register(mcp, config)

        mock_run.return_value = MagicMock(returncode=0, stdout="")
        registered["run_command"]("echo test")
        assert mock_run.call_args[1]["timeout"] == 120


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestErrorHandling:
    """Error conditions."""

    def test_empty_command(self, tools: dict) -> None:
        result = tools["run_command"]("")
        assert "Error" in result

    @patch("subprocess.run")
    def test_nonzero_exit(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.return_value = MagicMock(returncode=1, stderr="file not found")
        result = tools["run_command"]("ls nonexistent")
        assert "Command failed" in result
        assert "exit 1" in result

    @patch("subprocess.run")
    def test_timeout_expired(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(["echo"], 30)
        result = tools["run_command"]("echo test")
        assert "timed out" in result
        assert "30" in result

    @patch("subprocess.run")
    def test_generic_exception(self, mock_run: MagicMock, tools: dict) -> None:
        mock_run.side_effect = OSError("Permission denied")
        result = tools["run_command"]("ls")
        assert "Error executing command" in result

    def test_shlex_parse_error(self, tools: dict) -> None:
        """Unmatched quote causes shlex error."""
        result = tools["run_command"]("echo 'unterminated")
        assert "Error" in result


# ---------------------------------------------------------------------------
# register function
# ---------------------------------------------------------------------------
class TestRegister:
    """Verify register adds expected tools."""

    def test_registers_one_tool(self, tools: dict) -> None:
        assert set(tools.keys()) == {"run_command"}
