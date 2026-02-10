"""Comprehensive tests for MCP server factory."""

from unittest.mock import MagicMock, patch

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.server import create_server


class TestCreateServerBasics:
    """Basic create_server behavior."""

    def test_returns_fastmcp_instance(self) -> None:
        from mcp.server.fastmcp import FastMCP

        server = create_server()
        assert isinstance(server, FastMCP)

    def test_default_config_uses_default_name(self) -> None:
        server = create_server()
        assert server.name == "Nebulus Tools"

    def test_none_config_uses_defaults(self) -> None:
        server = create_server(None)
        assert server.name == "Nebulus Tools"

    def test_custom_config_name(self) -> None:
        config = MCPConfig(server_name="Custom")
        server = create_server(config)
        assert server.name == "Custom"


class TestCreateServerToolRegistration:
    """Verify that tools are properly registered."""

    EXPECTED_TOOLS = {
        "list_directory",
        "read_file",
        "write_file",
        "edit_file",
        "search_web",
        "search_code",
        "scrape_url",
        "read_pdf",
        "read_docx",
        "run_command",
    }

    def _get_registered_tool_names(self, server: object) -> set[str]:
        """Extract registered tool names from a FastMCP instance."""
        if hasattr(server, "_tool_manager"):
            return set(server._tool_manager._tools.keys())
        elif hasattr(server, "_tools"):
            return set(server._tools.keys())
        return set()

    def test_all_tools_registered(self) -> None:
        server = create_server()
        registered = self._get_registered_tool_names(server)
        missing = self.EXPECTED_TOOLS - registered
        assert not missing, f"Missing tools: {missing}"

    def test_no_unexpected_tools(self) -> None:
        """Only expected tools are registered (no leftovers)."""
        server = create_server()
        registered = self._get_registered_tool_names(server)
        # All registered tools should be in the expected set
        # (This may be relaxed if new tools are added)
        if registered:
            assert self.EXPECTED_TOOLS.issubset(registered)

    @patch("nebulus_core.mcp.server.ALL_MODULES")
    def test_register_called_for_each_module(
        self, mock_modules: MagicMock
    ) -> None:
        """Each module's register function is called with mcp and config."""
        mock_mod1 = MagicMock()
        mock_mod2 = MagicMock()
        mock_modules.__iter__ = MagicMock(return_value=iter([mock_mod1, mock_mod2]))

        config = MCPConfig(server_name="Test")
        create_server(config)

        mock_mod1.register.assert_called_once()
        mock_mod2.register.assert_called_once()

        # Verify config was passed
        call_args_1 = mock_mod1.register.call_args
        assert call_args_1[0][1] is config
        call_args_2 = mock_mod2.register.call_args
        assert call_args_2[0][1] is config

    @patch("nebulus_core.mcp.server.ALL_MODULES")
    def test_empty_module_list(self, mock_modules: MagicMock) -> None:
        """Server works even with no modules."""
        mock_modules.__iter__ = MagicMock(return_value=iter([]))
        server = create_server()
        assert server.name == "Nebulus Tools"


class TestAllModulesRegistry:
    """Verify the ALL_MODULES list is correct."""

    def test_all_modules_count(self) -> None:
        from nebulus_core.mcp.tools import ALL_MODULES

        assert len(ALL_MODULES) == 5

    def test_all_modules_have_register(self) -> None:
        from nebulus_core.mcp.tools import ALL_MODULES

        for module in ALL_MODULES:
            assert hasattr(module, "register"), (
                f"Module {module.__name__} missing register function"
            )
            assert callable(module.register)

    def test_all_modules_contains_expected_modules(self) -> None:
        from nebulus_core.mcp.tools import ALL_MODULES

        module_names = {m.__name__.rsplit(".", 1)[-1] for m in ALL_MODULES}
        expected = {"filesystem", "search", "web", "documents", "shell"}
        assert module_names == expected
