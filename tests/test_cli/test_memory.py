"""Tests for CLI memory management commands."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nebulus_core.cli.commands.memory import memory_group


def _invoke(
    args: list[str], adapter: MagicMock | None = None, console: MagicMock | None = None
) -> object:
    """Invoke memory group with a mock adapter in context."""
    if adapter is None:
        adapter = MagicMock()
        adapter.data_dir = "/tmp/test-data"
        adapter.chroma_settings = {"mode": "embedded", "path": "/tmp/test-chroma"}
        adapter.llm_base_url = "http://localhost:9999/v1"
        adapter.default_model = "test-model"
    console = console or MagicMock()
    runner = CliRunner()
    return runner.invoke(
        memory_group,
        args,
        obj={"adapter": adapter, "console": console},
    )


class TestMemoryStatus:
    """Tests for the memory status command."""

    @patch("nebulus_core.vector.client.VectorClient")
    @patch("nebulus_core.memory.graph_store.GraphStore")
    def test_shows_graph_and_vector_stats(
        self, mock_graph_cls: MagicMock, mock_vec_cls: MagicMock
    ) -> None:
        """status shows graph stats and vector store collections."""
        mock_graph = MagicMock()
        mock_stats = MagicMock()
        mock_stats.node_count = 42
        mock_stats.edge_count = 17
        mock_stats.entity_types = ["Server", "Person"]
        mock_graph.get_stats.return_value = mock_stats
        mock_graph_cls.return_value = mock_graph

        mock_vec = MagicMock()
        mock_vec.list_collections.return_value = ["ltm_episodic_memory", "docs"]
        mock_vec_cls.return_value = mock_vec

        console = MagicMock()
        _invoke(["status"], console=console)

        calls = [str(c) for c in console.print.call_args_list]
        joined = " ".join(calls)
        assert "42" in joined
        assert "17" in joined
        assert "2 collections" in joined

    @patch(
        "nebulus_core.vector.client.VectorClient",
        side_effect=RuntimeError("connection refused"),
    )
    @patch(
        "nebulus_core.memory.graph_store.GraphStore",
        side_effect=RuntimeError("file not found"),
    )
    def test_shows_unavailable_when_not_reachable(
        self, mock_graph_cls: MagicMock, mock_vec_cls: MagicMock
    ) -> None:
        """status shows 'unavailable' when graph/vector not reachable."""
        console = MagicMock()
        _invoke(["status"], console=console)

        calls = [str(c) for c in console.print.call_args_list]
        joined = " ".join(calls)
        assert "unavailable" in joined


class TestMemoryConsolidate:
    """Tests for the memory consolidate command."""

    @patch("nebulus_core.memory.consolidator.Consolidator")
    @patch("nebulus_core.llm.client.LLMClient")
    @patch("nebulus_core.memory.graph_store.GraphStore")
    @patch("nebulus_core.vector.episodic.EpisodicMemory")
    @patch("nebulus_core.vector.client.VectorClient")
    def test_runs_full_consolidation_flow(
        self,
        mock_vec_cls: MagicMock,
        mock_ep_cls: MagicMock,
        mock_graph_cls: MagicMock,
        mock_llm_cls: MagicMock,
        mock_consol_cls: MagicMock,
    ) -> None:
        """consolidate runs full flow with mocked dependencies."""
        mock_consolidator = MagicMock()
        mock_consolidator.consolidate.return_value = "Processed 5 memories"
        mock_consol_cls.return_value = mock_consolidator

        console = MagicMock()
        _invoke(["consolidate"], console=console)

        mock_consolidator.consolidate.assert_called_once()
        calls = [str(c) for c in console.print.call_args_list]
        joined = " ".join(calls)
        assert "Processed 5 memories" in joined

    @patch(
        "nebulus_core.vector.client.VectorClient",
        side_effect=RuntimeError("connection refused"),
    )
    def test_shows_error_when_consolidation_fails(
        self, mock_vec_cls: MagicMock
    ) -> None:
        """consolidate shows error when consolidation fails."""
        console = MagicMock()
        _invoke(["consolidate"], console=console)

        calls = [str(c) for c in console.print.call_args_list]
        joined = " ".join(calls)
        assert "Consolidation failed" in joined
