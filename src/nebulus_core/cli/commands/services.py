"""Service management commands: up, down, restart, logs, status."""

import click
import httpx
from rich.console import Console
from rich.table import Table

from nebulus_core.platform.base import PlatformAdapter


def check_status(adapter: PlatformAdapter, console: Console) -> None:
    """Check health of all services and display status table.

    Args:
        adapter: The active platform adapter.
        console: Rich console for output.
    """
    table = Table(title=f"Nebulus {adapter.platform_name.title()} Status")
    table.add_column("Service", style="cyan")
    table.add_column("Port", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Description")

    for svc in adapter.services:
        try:
            resp = httpx.get(svc.health_endpoint, timeout=5.0)
            if resp.status_code < 400:
                status = "[green]ONLINE[/green]"
            else:
                status = f"[yellow]HTTP {resp.status_code}[/yellow]"
        except httpx.ConnectError:
            status = "[red]OFFLINE[/red]"
        except httpx.TimeoutException:
            status = "[yellow]TIMEOUT[/yellow]"
        except Exception:
            status = "[red]ERROR[/red]"

        table.add_row(svc.name, str(svc.port), status, svc.description)

    console.print(table)


@click.group("service")
def services_group() -> None:
    """Manage platform services."""
    pass


@services_group.command()
@click.pass_context
def up(ctx: click.Context) -> None:
    """Start all services."""
    adapter = ctx.obj["adapter"]
    console = ctx.obj["console"]
    console.print(f"Starting Nebulus {adapter.platform_name.title()} services...")
    adapter.start_services()
    console.print("[green]Services started.[/green]")


@services_group.command()
@click.pass_context
def down(ctx: click.Context) -> None:
    """Stop all services."""
    adapter = ctx.obj["adapter"]
    console = ctx.obj["console"]
    console.print(f"Stopping Nebulus {adapter.platform_name.title()} services...")
    adapter.stop_services()
    console.print("[green]Services stopped.[/green]")


@services_group.command()
@click.option("--service", "-s", default=None, help="Specific service to restart.")
@click.pass_context
def restart(ctx: click.Context, service: str | None) -> None:
    """Restart one or all services.

    Args:
        service: Specific service name, or all if omitted.
    """
    adapter = ctx.obj["adapter"]
    console = ctx.obj["console"]
    target = service or "all services"
    console.print(f"Restarting {target}...")
    adapter.restart_services(service)
    console.print(f"[green]{target.title()} restarted.[/green]")


@services_group.command()
@click.argument("service")
@click.option("--follow", "-f", is_flag=True, help="Follow log output.")
@click.pass_context
def logs(ctx: click.Context, service: str, follow: bool) -> None:
    """Stream logs for a service.

    Args:
        service: Service name to get logs for.
        follow: Whether to follow/tail the output.
    """
    adapter = ctx.obj["adapter"]
    adapter.get_logs(service, follow=follow)
