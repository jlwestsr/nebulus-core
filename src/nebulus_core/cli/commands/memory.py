"""Memory management commands."""

import click
from rich.console import Console


@click.group("memory")
def memory_group() -> None:
    """Manage long-term memory systems."""
    pass


@memory_group.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show LTM system status and metrics."""
    console: Console = ctx.obj["console"]

    # Lazy import to avoid startup cost when not used
    from nebulus_core.memory.graph_store import GraphStore

    adapter = ctx.obj["adapter"]
    chroma_settings = adapter.chroma_settings

    # Graph store status
    try:
        graph = GraphStore()
        stats = graph.get_stats()
        console.print(
            f"[cyan]Knowledge Graph:[/cyan] {stats.node_count} nodes, "
            f"{stats.edge_count} edges"
        )
        if stats.entity_types:
            console.print(f"  Entity types: {', '.join(stats.entity_types)}")
    except Exception as e:
        console.print(f"[yellow]Knowledge Graph:[/yellow] unavailable ({e})")

    # Vector store status
    try:
        from nebulus_core.vector.client import VectorClient

        vec = VectorClient(settings=chroma_settings)
        collections = vec.list_collections()
        console.print(f"[cyan]Vector Store:[/cyan] {len(collections)} collections")
        for col in collections:
            console.print(f"  - {col}")
    except Exception as e:
        console.print(f"[yellow]Vector Store:[/yellow] unavailable ({e})")


@memory_group.command()
@click.pass_context
def consolidate(ctx: click.Context) -> None:
    """Trigger manual memory consolidation cycle."""
    console: Console = ctx.obj["console"]
    adapter = ctx.obj["adapter"]

    console.print("[cyan]Starting memory consolidation...[/cyan]")

    try:
        from nebulus_core.memory.consolidator import Consolidator

        c = Consolidator(
            chroma_settings=adapter.chroma_settings,
            llm_base_url=adapter.llm_base_url,
        )
        result = c.run()
        console.print(f"[green]Consolidation complete.[/green] {result}")
    except Exception as e:
        console.print(f"[red]Consolidation failed:[/red] {e}")
