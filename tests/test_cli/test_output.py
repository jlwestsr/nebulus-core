"""Tests for Rich output formatting helpers."""

from rich.console import Console
from rich.table import Table

from nebulus_core.cli.output import create_status_table, print_banner


class TestPrintBanner:
    """Tests for the print_banner() helper."""

    def test_outputs_platform_name_and_version(self) -> None:
        """print_banner outputs platform name and version."""
        console = Console(file=None, force_terminal=True)
        # Should not raise — smoke test for rendering
        print_banner(console, "prime", "0.1.0")


class TestCreateStatusTable:
    """Tests for the create_status_table() helper."""

    def test_returns_table_with_correct_columns(self) -> None:
        """create_status_table returns a table with the expected columns."""
        table = create_status_table("Test Status")
        assert isinstance(table, Table)
        assert table.title == "Test Status"
        column_names = [col.header for col in table.columns]
        assert "Service" in column_names
        assert "Port" in column_names
        assert "Status" in column_names
        assert "Description" in column_names
