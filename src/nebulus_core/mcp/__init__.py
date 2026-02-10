"""MCP tool server for the Nebulus ecosystem.

Provides platform-agnostic MCP tools (filesystem, search, web scraping,
document parsing, shell execution) that can be assembled into a FastMCP
server by any platform project.
"""

from nebulus_core.mcp.config import MCPConfig
from nebulus_core.mcp.server import create_server

__all__ = ["MCPConfig", "create_server"]
