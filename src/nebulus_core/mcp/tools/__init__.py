"""MCP tool modules for Nebulus.

Each module provides a ``register(mcp, config)`` function that adds
tools to a FastMCP server instance.
"""

from nebulus_core.mcp.tools import (
    documents,
    filesystem,
    search,
    shell,
    web,
)

ALL_MODULES = [filesystem, search, web, documents, shell]

__all__ = ["ALL_MODULES", "documents", "filesystem", "search", "shell", "web"]
