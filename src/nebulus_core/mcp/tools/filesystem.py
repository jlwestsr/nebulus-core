"""Filesystem tools — list, read, write, and edit files within a workspace."""

import os

from mcp.server.fastmcp import FastMCP

from nebulus_core.mcp.config import MCPConfig


def _validate_path(path: str, config: MCPConfig) -> str:
    """Validate and return absolute path within the workspace.

    Args:
        path: Relative path to validate.
        config: MCP configuration with workspace_path.

    Returns:
        Resolved absolute path.

    Raises:
        ValueError: If path escapes the workspace.
    """
    base_path = str(config.workspace_path)
    target_path = os.path.join(base_path, path.lstrip("/"))

    if not os.path.abspath(target_path).startswith(base_path):
        raise ValueError(f"Access denied. Cannot access paths outside {base_path}.")

    return target_path


def register(mcp: FastMCP, config: MCPConfig) -> None:
    """Register filesystem tools on the MCP server.

    Args:
        mcp: FastMCP server instance.
        config: MCP configuration.
    """

    @mcp.tool()
    def list_directory(path: str = ".") -> str:
        """List contents of a directory in the workspace."""
        try:
            target_path = _validate_path(path, config)
            items = os.listdir(target_path)
            return "\n".join(items) if items else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {str(e)}"

    @mcp.tool()
    def read_file(path: str) -> str:
        """Read file content from the workspace."""
        try:
            target_path = _validate_path(path, config)
            with open(target_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {str(e)}"

    @mcp.tool()
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the workspace (overwrites if exists)."""
        try:
            target_path = _validate_path(path, config)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"

    @mcp.tool()
    def edit_file(path: str, target_text: str, replacement_text: str) -> str:
        """Edit a file by replacing the first occurrence of target_text."""
        try:
            target_path = _validate_path(path, config)
            if not os.path.exists(target_path):
                return f"Error: File {path} not found."

            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            if content.find(target_text) == -1:
                return f"Error: Target text missing from {path}"

            new_content = content.replace(target_text, replacement_text, 1)

            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully edited {path}"
        except Exception as e:
            return f"Error editing file: {str(e)}"
