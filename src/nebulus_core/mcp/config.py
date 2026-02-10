"""MCP server configuration model."""

from pathlib import Path

from pydantic import BaseModel


class MCPConfig(BaseModel):
    """Configuration for a Nebulus MCP tool server.

    Args:
        server_name: Display name for the MCP server.
        workspace_path: Root directory for file operations.
        allowed_commands: Shell commands permitted by run_command.
        blocked_operators: Shell operators blocked for security.
        command_timeout: Max seconds for subprocess execution.
        google_api_key: Optional Google Custom Search API key.
        google_cse_id: Optional Google Custom Search Engine ID.
    """

    server_name: str = "Nebulus Tools"
    workspace_path: Path = Path.cwd()
    allowed_commands: set[str] = {
        "ls",
        "grep",
        "cat",
        "find",
        "pytest",
        "git",
        "echo",
        "pwd",
        "tree",
    }
    blocked_operators: set[str] = {">", ">>", "&", "|", ";", "`", "$("}
    command_timeout: int = 30
    google_api_key: str | None = None
    google_cse_id: str | None = None
