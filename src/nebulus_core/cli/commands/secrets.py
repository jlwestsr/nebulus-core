"""Secrets management CLI commands."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from nebulus_core.security import (
    audit_secrets_in_path,
    get_secret,
    store_secret,
    delete_secret,
    list_secrets as list_all_secrets,
    audit_secrets as get_audit_info,
    migrate_secrets,
)

console = Console()


@click.group("secrets")
def secrets_group() -> None:
    """Manage encrypted secrets storage."""
    pass


@secrets_group.command("store")
@click.argument("key")
@click.option("--value", prompt=True, hide_input=True, help="Secret value to store")
def store_cmd(key: str, value: str) -> None:
    """Store a secret securely.

    KEY: Identifier for the secret (e.g., 'openai_api_key')
    """
    try:
        store_secret(key, value)
        console.print(f"[green]✓[/green] Secret '{key}' stored successfully")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("get")
@click.argument("key")
@click.option("--show", is_flag=True, help="Display the secret value (use with caution)")
def get_cmd(key: str, show: bool) -> None:
    """Retrieve a secret.

    KEY: Identifier for the secret to retrieve
    """
    try:
        value = get_secret(key)
        if value is None:
            console.print(f"[yellow]Secret '{key}' not found[/yellow]")
        elif show:
            console.print(f"[cyan]{key}:[/cyan] {value}")
        else:
            console.print(
                f"[cyan]{key}:[/cyan] ****** (use --show to display value)"
            )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("delete")
@click.argument("key")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_cmd(key: str, yes: bool) -> None:
    """Delete a secret.

    KEY: Identifier for the secret to delete
    """
    if not yes:
        if not click.confirm(f"Delete secret '{key}'?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        if delete_secret(key):
            console.print(f"[green]✓[/green] Secret '{key}' deleted")
        else:
            console.print(f"[yellow]Secret '{key}' not found[/yellow]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("list")
def list_cmd() -> None:
    """List all stored secret keys."""
    try:
        keys = list_all_secrets()
        if not keys:
            console.print("[yellow]No secrets stored[/yellow]")
            return

        table = Table(title="Stored Secrets")
        table.add_column("Key", style="cyan")
        table.add_column("Status", style="green")

        for key in sorted(keys):
            table.add_row(key, "✓ stored")

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("info")
def info_cmd() -> None:
    """Display secrets storage backend information."""
    try:
        info = get_audit_info()

        table = Table(title="Secrets Storage Info")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Backend", info["backend"])
        table.add_row("Secret Count", str(info["secret_count"]))

        console.print(table)

        if info["keys"]:
            console.print("\n[bold]Stored Keys:[/bold]")
            for key in sorted(info["keys"]):
                console.print(f"  • {key}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("audit")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Scan subdirectories recursively",
)
def audit_cmd(path: str, recursive: bool) -> None:
    """Scan for plaintext secrets in files.

    PATH: Directory or file to scan (default: current directory)
    """
    try:
        findings = audit_secrets_in_path(Path(path), recursive=recursive)

        if not findings:
            console.print("[green]✓[/green] No plaintext secrets detected")
            return

        # Group by severity
        high = [f for f in findings if f.severity == "HIGH"]
        medium = [f for f in findings if f.severity == "MEDIUM"]

        console.print(f"\n[red bold]Found {len(findings)} potential secrets:[/red bold]\n")

        if high:
            console.print(f"[red bold]HIGH severity: {len(high)}[/red bold]")
            for finding in high:
                console.print(
                    f"  [red]✗[/red] {finding.file_path}:{finding.line_number} "
                    f"({finding.pattern_type})"
                )
                console.print(f"    {finding.context[:80]}")

        if medium:
            console.print(f"\n[yellow bold]MEDIUM severity: {len(medium)}[/yellow bold]")
            for finding in medium:
                console.print(
                    f"  [yellow]![/yellow] {finding.file_path}:{finding.line_number} "
                    f"({finding.pattern_type})"
                )
                console.print(f"    {finding.context[:80]}")

        # Exit with error code if secrets found
        raise click.Abort()

    except click.Abort:
        raise
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()


@secrets_group.command("migrate")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Scan subdirectories recursively",
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def migrate_cmd(path: str, recursive: bool, yes: bool) -> None:
    """Migrate plaintext secrets from config files to encrypted storage.

    PATH: Directory or file to process (default: current directory)

    Scans .env, .yml, and .yaml files for key-value pairs that appear to be
    secrets and migrates them to the encrypted secrets store.
    """
    if not yes:
        console.print(
            "[yellow]This will scan config files and store detected secrets.[/yellow]"
        )
        if not click.confirm("Continue?"):
            console.print("[yellow]Cancelled[/yellow]")
            return

    try:
        result = migrate_secrets(Path(path), recursive=recursive)

        if result.secrets_migrated == 0:
            console.print("[yellow]No secrets found to migrate[/yellow]")
            return

        # Display results
        console.print(
            f"\n[green]✓[/green] Migration complete: "
            f"{result.secrets_migrated} secrets migrated"
        )

        if result.source_files:
            console.print("\n[bold]Source files:[/bold]")
            for file_path in result.source_files:
                console.print(f"  • {file_path}")

        if result.errors:
            console.print(f"\n[yellow]Errors ({len(result.errors)}):[/yellow]")
            for error in result.errors:
                console.print(f"  [red]✗[/red] {error}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise click.Abort()
