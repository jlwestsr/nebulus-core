"""CLI entry point with platform auto-detection."""

import sys

import click
from rich.console import Console

from nebulus_core import __version__
from nebulus_core.cli.commands.services import services_group
from nebulus_core.cli.commands.models import models_group
from nebulus_core.cli.commands.memory import memory_group
from nebulus_core.platform import detect_platform, load_adapter

console = Console()

# Global adapter reference, set during CLI init
_adapter = None


def get_adapter():
    """Get the current platform adapter.

    Returns:
        The active PlatformAdapter instance.

    Raises:
        RuntimeError: If the CLI has not been initialized.
    """
    if _adapter is None:
        raise RuntimeError("Platform adapter not initialized.")
    return _adapter


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nebulus")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Nebulus AI Ecosystem CLI.

    Manages local AI services across Linux (Prime) and macOS (Edge).
    """
    global _adapter

    try:
        platform_name = detect_platform()
        _adapter = load_adapter(platform_name)
    except RuntimeError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    ctx.ensure_object(dict)
    ctx.obj["adapter"] = _adapter
    ctx.obj["console"] = console

    # Register platform-specific commands
    for cmd in _adapter.platform_specific_commands():
        cli.add_command(cmd)

    # Default action: show status
    if ctx.invoked_subcommand is None:
        ctx.invoke(status)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show health status of all services."""
    from nebulus_core.cli.commands.services import check_status

    check_status(ctx.obj["adapter"], ctx.obj["console"])


cli.add_command(services_group, "service")
cli.add_command(models_group, "model")
cli.add_command(memory_group, "memory")
