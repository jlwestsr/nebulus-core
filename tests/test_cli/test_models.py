"""Tests for CLI model management commands."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nebulus_core.cli.commands.models import models_group


def _invoke(args: list[str], adapter: MagicMock | None = None) -> object:
    """Invoke model group with a mock adapter in context."""
    if adapter is None:
        adapter = MagicMock()
        adapter.llm_base_url = "http://localhost:9999/v1"
    runner = CliRunner()
    return runner.invoke(
        models_group,
        args,
        obj={"adapter": adapter, "console": MagicMock()},
    )


class TestListModels:
    """Tests for the model list command."""

    @patch("nebulus_core.cli.commands.models.LLMClient")
    def test_renders_table_when_models_available(
        self, mock_client_cls: MagicMock
    ) -> None:
        """list_models renders a table when models are available."""
        mock_client = MagicMock()
        mock_client.list_models.return_value = [
            {"id": "llama-3.1-8b", "owned_by": "meta"},
            {"id": "codellama-7b", "owned_by": "meta"},
        ]
        mock_client_cls.return_value = mock_client

        adapter = MagicMock()
        adapter.llm_base_url = "http://localhost:5000/v1"
        result = _invoke(["list"], adapter)

        assert result.exit_code == 0
        mock_client.list_models.assert_called_once()

    @patch("nebulus_core.cli.commands.models.LLMClient")
    def test_shows_error_when_engine_unreachable(
        self, mock_client_cls: MagicMock
    ) -> None:
        """list_models shows error when inference engine is unreachable."""
        mock_client = MagicMock()
        mock_client.list_models.side_effect = ConnectionError("refused")
        mock_client_cls.return_value = mock_client

        adapter = MagicMock()
        adapter.llm_base_url = "http://localhost:5000/v1"
        runner = CliRunner()
        console = MagicMock()
        result = runner.invoke(
            models_group,
            ["list"],
            obj={"adapter": adapter, "console": console},
        )

        assert result.exit_code == 0
        console.print.assert_called_once()
        call_str = str(console.print.call_args)
        assert "Failed to connect" in call_str

    @patch("nebulus_core.cli.commands.models.LLMClient")
    def test_shows_no_models_for_empty_list(self, mock_client_cls: MagicMock) -> None:
        """list_models shows 'No models found' for empty list."""
        mock_client = MagicMock()
        mock_client.list_models.return_value = []
        mock_client_cls.return_value = mock_client

        adapter = MagicMock()
        adapter.llm_base_url = "http://localhost:5000/v1"
        runner = CliRunner()
        console = MagicMock()
        result = runner.invoke(
            models_group,
            ["list"],
            obj={"adapter": adapter, "console": console},
        )

        assert result.exit_code == 0
        console.print.assert_called_once()
        call_str = str(console.print.call_args)
        assert "No models found" in call_str
