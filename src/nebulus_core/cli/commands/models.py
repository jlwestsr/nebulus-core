"""Model management commands."""

import click
from rich.console import Console
from rich.table import Table

from nebulus_core.llm.client import LLMClient


@click.group("model")
def models_group() -> None:
    """Manage LLM models."""
    pass


@models_group.command("list")
@click.pass_context
def list_models(ctx: click.Context) -> None:
    """List available models on the inference engine."""
    adapter = ctx.obj["adapter"]
    console: Console = ctx.obj["console"]

    client = LLMClient(base_url=adapter.llm_base_url)

    try:
        models = client.list_models()
    except Exception as e:
        console.print(f"[red]Failed to connect to inference engine:[/red] {e}")
        return

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        return

    table = Table(title="Available Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Owned By", style="magenta")

    for model in models:
        table.add_row(
            model.get("id", "unknown"),
            model.get("owned_by", "unknown"),
        )

    console.print(table)
