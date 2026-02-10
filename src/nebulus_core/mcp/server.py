"""MCP server factory — assembles a FastMCP instance with all core tools."""

from mcp.server.fastmcp import FastMCP

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.tools import ALL_MODULES


def create_server(config: MCPConfig | None = None) -> FastMCP:
    """Create a configured MCP server with all core tools registered.

    Args:
        config: Server configuration. Uses defaults if not provided.

    Returns:
        A FastMCP instance with all core tools registered.
    """
    if config is None:
        config = MCPConfig()

    mcp = FastMCP(config.server_name)

    for module in ALL_MODULES:
        module.register(mcp, config)

    return mcp
