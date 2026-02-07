"""Tests for CLI entry point and bootstrap behavior."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nebulus_core.cli.main import cli, get_adapter


class TestGetAdapter:
    """Tests for the get_adapter helper."""

    def test_get_adapter_raises_before_init(self) -> None:
        """get_adapter should raise RuntimeError before CLI init."""
        import nebulus_core.cli.main as main_mod

        original = main_mod._adapter
        try:
            main_mod._adapter = None
            with pytest.raises(RuntimeError, match="not initialized"):
                get_adapter()
        finally:
            main_mod._adapter = original


class TestCLIBootstrap:
    """Tests for CLI startup with and without adapters."""

    def test_cli_shows_error_when_no_adapter(self) -> None:
        """CLI should show a helpful error and exit 1 when no adapter."""
        runner = CliRunner()
        with patch(
            "nebulus_core.cli.main.load_adapter",
            side_effect=RuntimeError("No adapter found for platform: prime"),
        ):
            result = runner.invoke(cli)
            assert result.exit_code == 1
            assert "No adapter found" in result.output

    def test_cli_shows_error_on_detection_failure(self) -> None:
        """CLI should show error when platform detection fails."""
        runner = CliRunner()
        with patch(
            "nebulus_core.cli.main.detect_platform",
            side_effect=RuntimeError("Unsupported platform"),
        ):
            result = runner.invoke(cli)
            assert result.exit_code == 1
            assert "Unsupported platform" in result.output

    def test_cli_version_option(self) -> None:
        """--version should print version and exit cleanly."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "nebulus" in result.output
