"""Comprehensive tests for MCPConfig model."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from nebulus_core.mcp.config import MCPConfig


class TestMCPConfigDefaults:
    """Verify all default values are correct."""

    def test_server_name_default(self) -> None:
        config = MCPConfig()
        assert config.server_name == "Nebulus Tools"

    def test_workspace_path_defaults_to_cwd(self) -> None:
        config = MCPConfig()
        assert config.workspace_path == Path.cwd()

    def test_command_timeout_default(self) -> None:
        config = MCPConfig()
        assert config.command_timeout == 30

    def test_google_api_key_default_none(self) -> None:
        config = MCPConfig()
        assert config.google_api_key is None

    def test_google_cse_id_default_none(self) -> None:
        config = MCPConfig()
        assert config.google_cse_id is None

    def test_allowed_commands_default(self) -> None:
        config = MCPConfig()
        expected = {"ls", "grep", "cat", "find", "pytest", "git", "echo", "pwd", "tree"}
        assert config.allowed_commands == expected

    def test_blocked_operators_default(self) -> None:
        config = MCPConfig()
        expected = {">", ">>", "&", "|", ";", "`", "$("}
        assert config.blocked_operators == expected


class TestMCPConfigCustomValues:
    """Verify custom configuration is accepted and stored."""

    def test_custom_server_name(self) -> None:
        config = MCPConfig(server_name="My Tools")
        assert config.server_name == "My Tools"

    def test_custom_workspace_path(self, tmp_path: Path) -> None:
        config = MCPConfig(workspace_path=tmp_path)
        assert config.workspace_path == tmp_path

    def test_workspace_path_coerced_from_string(self) -> None:
        config = MCPConfig(workspace_path="/tmp/test")
        assert isinstance(config.workspace_path, Path)
        assert config.workspace_path == Path("/tmp/test")

    def test_custom_allowed_commands(self) -> None:
        config = MCPConfig(allowed_commands={"echo", "pwd"})
        assert config.allowed_commands == {"echo", "pwd"}

    def test_empty_allowed_commands(self) -> None:
        config = MCPConfig(allowed_commands=set())
        assert config.allowed_commands == set()

    def test_custom_blocked_operators(self) -> None:
        config = MCPConfig(blocked_operators={"|", ";"})
        assert config.blocked_operators == {"|", ";"}

    def test_empty_blocked_operators(self) -> None:
        config = MCPConfig(blocked_operators=set())
        assert config.blocked_operators == set()

    def test_custom_command_timeout(self) -> None:
        config = MCPConfig(command_timeout=120)
        assert config.command_timeout == 120

    def test_google_api_key_set(self) -> None:
        config = MCPConfig(google_api_key="test-key-123")
        assert config.google_api_key == "test-key-123"

    def test_google_cse_id_set(self) -> None:
        config = MCPConfig(google_cse_id="cse-456")
        assert config.google_cse_id == "cse-456"

    def test_both_google_credentials(self) -> None:
        config = MCPConfig(google_api_key="key", google_cse_id="cse")
        assert config.google_api_key == "key"
        assert config.google_cse_id == "cse"


class TestMCPConfigEdgeCases:
    """Edge cases and type coercion."""

    def test_empty_server_name(self) -> None:
        config = MCPConfig(server_name="")
        assert config.server_name == ""

    def test_zero_timeout(self) -> None:
        config = MCPConfig(command_timeout=0)
        assert config.command_timeout == 0

    def test_all_fields_together(self, tmp_path: Path) -> None:
        config = MCPConfig(
            server_name="Full Config",
            workspace_path=tmp_path,
            allowed_commands={"echo"},
            blocked_operators={"|"},
            command_timeout=60,
            google_api_key="key",
            google_cse_id="cse",
        )
        assert config.server_name == "Full Config"
        assert config.workspace_path == tmp_path
        assert config.allowed_commands == {"echo"}
        assert config.blocked_operators == {"|"}
        assert config.command_timeout == 60
        assert config.google_api_key == "key"
        assert config.google_cse_id == "cse"

    def test_is_pydantic_basemodel(self) -> None:
        from pydantic import BaseModel

        assert issubclass(MCPConfig, BaseModel)

    def test_model_serialization_roundtrip(self, tmp_path: Path) -> None:
        """Config can be serialized to dict and back."""
        config = MCPConfig(
            server_name="Test",
            workspace_path=tmp_path,
            command_timeout=10,
        )
        data = config.model_dump()
        restored = MCPConfig(**data)
        assert restored.server_name == config.server_name
        assert restored.workspace_path == config.workspace_path
        assert restored.command_timeout == config.command_timeout
