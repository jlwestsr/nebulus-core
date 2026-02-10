"""Tests for MCPConfig model."""

from pathlib import Path

from nebulus_core.mcp.config import MCPConfig


class TestMCPConfig:
    """MCPConfig validation and defaults."""

    def test_defaults(self) -> None:
        config = MCPConfig()
        assert config.server_name == "Nebulus Tools"
        assert config.command_timeout == 30
        assert config.google_api_key is None
        assert config.google_cse_id is None

    def test_default_allowed_commands(self) -> None:
        config = MCPConfig()
        expected = {"ls", "grep", "cat", "find", "pytest", "git", "echo", "pwd", "tree"}
        assert config.allowed_commands == expected

    def test_default_blocked_operators(self) -> None:
        config = MCPConfig()
        expected = {">", ">>", "&", "|", ";", "`", "$("}
        assert config.blocked_operators == expected

    def test_custom_workspace(self, tmp_path: Path) -> None:
        config = MCPConfig(workspace_path=tmp_path)
        assert config.workspace_path == tmp_path

    def test_custom_server_name(self) -> None:
        config = MCPConfig(server_name="Black Box Tools")
        assert config.server_name == "Black Box Tools"

    def test_custom_allowed_commands(self) -> None:
        config = MCPConfig(allowed_commands={"ls", "echo"})
        assert config.allowed_commands == {"ls", "echo"}

    def test_google_credentials(self) -> None:
        config = MCPConfig(
            google_api_key="key123",
            google_cse_id="cse456",
        )
        assert config.google_api_key == "key123"
        assert config.google_cse_id == "cse456"

    def test_workspace_path_is_path_object(self) -> None:
        config = MCPConfig(workspace_path="/tmp/test")
        assert isinstance(config.workspace_path, Path)
