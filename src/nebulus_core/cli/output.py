"""Rich output formatting helpers."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def print_banner(console: Console, platform_name: str, version: str) -> None:
    """Print the Nebulus startup banner.

    Args:
        console: Rich console for output.
        platform_name: Active platform name.
        version: Package version string.
    """
    console.print(
        Panel(
            f"[bold cyan]Nebulus {platform_name.title()}[/bold cyan] v{version}",
            subtitle="Local AI Ecosystem",
            border_style="cyan",
        )
    )


def create_status_table(title: str) -> Table:
    """Create a standard status table.

    Args:
        title: Table title.

    Returns:
        Configured Rich Table.
    """
    table = Table(title=title)
    table.add_column("Service", style="cyan")
    table.add_column("Port", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Description")
    return table
