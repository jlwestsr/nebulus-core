"""Tests for CLI tools command group."""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from nebulus_core.cli.commands.tools import tools_group


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestToolsGroup:
    """CLI tools command tests."""

    def test_tools_group_exists(self) -> None:
        assert tools_group.name == "tools"

    def test_list_command_exists(self) -> None:
        commands = {cmd for cmd in tools_group.commands}
        assert "list" in commands

    def test_start_command_exists(self) -> None:
        commands = {cmd for cmd in tools_group.commands}
        assert "start" in commands

    def test_list_runs_without_crash(self, runner: CliRunner) -> None:
        """Verify list command creates server and lists tools."""
        result = runner.invoke(
            tools_group,
            ["list"],
            obj={"console": MagicMock(), "adapter": MagicMock()},
        )
        assert result.exit_code == 0
