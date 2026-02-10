"""Tests for MCP server factory."""

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.server import create_server


class TestCreateServer:
    """create_server factory tests."""

    def test_returns_fastmcp_instance(self) -> None:
        from mcp.server.fastmcp import FastMCP

        server = create_server()
        assert isinstance(server, FastMCP)

    def test_default_config(self) -> None:
        server = create_server()
        assert server.name == "Nebulus Tools"

    def test_custom_config(self) -> None:
        config = MCPConfig(server_name="Custom Server")
        server = create_server(config)
        assert server.name == "Custom Server"

    def test_registers_tools(self) -> None:
        server = create_server()
        # list_tools is async in newer FastMCP — we check the internal registry
        # FastMCP stores tools in _tool_manager
        tool_names = {
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
        # Access the registered tools — FastMCP may expose via different attrs
        # depending on version. Try common patterns.
        registered = set()
        if hasattr(server, "_tool_manager"):
            registered = set(server._tool_manager._tools.keys())
        elif hasattr(server, "_tools"):
            registered = set(server._tools.keys())

        assert tool_names.issubset(
            registered
        ), f"Missing tools: {tool_names - registered}"

    def test_none_config_uses_defaults(self) -> None:
        server = create_server(None)
        assert server.name == "Nebulus Tools"
