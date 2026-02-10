"""CLI commands for the MCP tool server."""

from pathlib import Path

import click


@click.group()
def tools_group() -> None:
    """Manage the MCP tool server."""
    pass


@tools_group.command("start")
@click.option("--host", default="0.0.0.0", help="Bind address.")
@click.option("--port", default=8002, type=int, help="Port to listen on.")
@click.pass_context
def start(ctx: click.Context, host: str, port: int) -> None:
    """Start the MCP tool server."""
    import uvicorn

    from nebulus_core.mcp import MCPConfig, create_server

    adapter = ctx.obj["adapter"]
    console = ctx.obj["console"]

    # Build config from adapter settings
    overrides = adapter.mcp_settings
    config = MCPConfig(
        workspace_path=overrides.get("workspace_path", Path.cwd()),
        server_name=overrides.get("server_name", "Nebulus Tools"),
        allowed_commands=overrides.get(
            "allowed_commands",
            MCPConfig.model_fields["allowed_commands"].default,
        ),
    )

    mcp = create_server(config)
    app = mcp.sse_app()

    console.print(
        f"[green]Starting MCP server[/green] "
        f"'{config.server_name}' on {host}:{port}"
    )
    console.print(f"[dim]Workspace: {config.workspace_path}[/dim]")

    uvicorn.run(app, host=host, port=port)


@tools_group.command("list")
@click.pass_context
def list_tools(ctx: click.Context) -> None:
    """List registered MCP tools."""
    import asyncio

    from nebulus_core.mcp import MCPConfig, create_server

    console = ctx.obj["console"]

    mcp = create_server(MCPConfig())

    console.print("[bold]Registered MCP tools:[/bold]\n")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        console.print(f"  [cyan]{tool.name}[/cyan] — {tool.description}")
