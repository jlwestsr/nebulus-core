"""Shell execution tool — run safe commands within the workspace."""

import shlex
import subprocess

from mcp.server.fastmcp import FastMCP

from nebulus_core.mcp.config import MCPConfig


def register(mcp: FastMCP, config: MCPConfig) -> None:
    """Register shell tools on the MCP server.

    Args:
        mcp: FastMCP server instance.
        config: MCP configuration.
    """

    @mcp.tool()
    def run_command(command: str) -> str:
        """Run a safe shell command in the workspace."""
        try:
            for op in config.blocked_operators:
                if op in command:
                    return f"Error: Operator '{op}' is not allowed for security."

            args = shlex.split(command)
            if not args:
                return "Error: Empty command."

            binary = args[0]
            if binary not in config.allowed_commands:
                return f"Error: Command '{binary}' is not allowed."

            result = subprocess.run(
                args,
                cwd=str(config.workspace_path),
                capture_output=True,
                text=True,
                timeout=config.command_timeout,
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return (
                    f"Command failed (exit {result.returncode}): " f"\n{result.stderr}"
                )

        except subprocess.TimeoutExpired:
            return (
                f"Error: Command timed out after " f"{config.command_timeout} seconds."
            )
        except Exception as e:
            return f"Error executing command: {str(e)}"
