"""Memory management commands."""

from pathlib import Path

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
    adapter = ctx.obj["adapter"]

    # Graph store status
    try:
        from nebulus_core.memory.graph_store import GraphStore

        graph_path = Path(adapter.data_dir) / "memory_graph.json"
        graph = GraphStore(storage_path=graph_path)
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

        vec = VectorClient(settings=adapter.chroma_settings)
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
        from nebulus_core.llm.client import LLMClient
        from nebulus_core.memory.consolidator import Consolidator
        from nebulus_core.memory.graph_store import GraphStore
        from nebulus_core.vector.client import VectorClient
        from nebulus_core.vector.episodic import EpisodicMemory

        vec_client = VectorClient(settings=adapter.chroma_settings)
        episodic = EpisodicMemory(vec_client)
        graph_path = Path(adapter.data_dir) / "memory_graph.json"
        graph = GraphStore(storage_path=graph_path)
        llm = LLMClient(base_url=adapter.llm_base_url)

        consolidator = Consolidator(
            episodic=episodic,
            graph=graph,
            llm=llm,
            model=adapter.default_model,
        )
        result = consolidator.consolidate()
        console.print(f"[green]Done.[/green] {result}")
    except Exception as e:
        console.print(f"[red]Consolidation failed:[/red] {e}")
