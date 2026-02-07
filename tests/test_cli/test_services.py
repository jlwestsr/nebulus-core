"""Tests for CLI service management commands."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nebulus_core.cli.commands.services import check_status, services_group
from nebulus_core.platform.base import ServiceInfo


def _make_adapter(services: list[ServiceInfo] | None = None) -> MagicMock:
    """Create a mock adapter with configurable services."""
    adapter = MagicMock()
    adapter.platform_name = "test"
    adapter.services = services or [
        ServiceInfo(
            name="api",
            port=8000,
            health_endpoint="http://localhost:8000/health",
            description="API server",
        ),
        ServiceInfo(
            name="chromadb",
            port=8001,
            health_endpoint="http://localhost:8001/api/v1/heartbeat",
            description="Vector store",
        ),
    ]
    return adapter


class TestCheckStatus:
    """Tests for the check_status() display function."""

    @patch("nebulus_core.cli.commands.services.httpx")
    def test_renders_table_with_service_info(self, mock_httpx: MagicMock) -> None:
        """check_status renders a table with service names, ports, and status."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_httpx.get.return_value = mock_resp
        mock_httpx.ConnectError = ConnectionError
        mock_httpx.TimeoutException = TimeoutError

        adapter = _make_adapter()
        console = MagicMock()
        check_status(adapter, console)

        console.print.assert_called_once()
        table = console.print.call_args[0][0]
        assert "Nebulus Test Status" in table.title
        assert len(table.rows) == 2

    @patch("nebulus_core.cli.commands.services.httpx")
    def test_shows_offline_for_connect_error(self, mock_httpx: MagicMock) -> None:
        """check_status shows OFFLINE for unreachable health endpoint."""
        mock_httpx.ConnectError = type("ConnectError", (Exception,), {})
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
        mock_httpx.get.side_effect = mock_httpx.ConnectError()

        adapter = _make_adapter()
        console = MagicMock()
        check_status(adapter, console)

        table = console.print.call_args[0][0]
        cells = [str(c) for col in table.columns for c in col._cells]
        assert any("OFFLINE" in c for c in cells)

    @patch("nebulus_core.cli.commands.services.httpx")
    def test_shows_timeout_for_slow_endpoint(self, mock_httpx: MagicMock) -> None:
        """check_status shows TIMEOUT for slow health endpoint."""
        mock_httpx.ConnectError = type("ConnectError", (Exception,), {})
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
        mock_httpx.get.side_effect = mock_httpx.TimeoutException()

        adapter = _make_adapter()
        console = MagicMock()
        check_status(adapter, console)

        table = console.print.call_args[0][0]
        cells = [str(c) for col in table.columns for c in col._cells]
        assert any("TIMEOUT" in c for c in cells)

    @patch("nebulus_core.cli.commands.services.httpx")
    def test_shows_error_for_unexpected_exception(self, mock_httpx: MagicMock) -> None:
        """check_status shows ERROR for unexpected exceptions."""
        mock_httpx.ConnectError = type("ConnectError", (Exception,), {})
        mock_httpx.TimeoutException = type("TimeoutException", (Exception,), {})
        mock_httpx.get.side_effect = RuntimeError("unexpected")

        adapter = _make_adapter()
        console = MagicMock()
        check_status(adapter, console)

        table = console.print.call_args[0][0]
        cells = [str(c) for col in table.columns for c in col._cells]
        assert any("ERROR" in c for c in cells)


class TestServiceCommands:
    """Tests for Click service subcommands (up, down, restart)."""

    def _invoke(self, args: list[str], adapter: MagicMock | None = None) -> object:
        """Invoke service group with a mock adapter in context."""
        adapter = adapter or _make_adapter()
        runner = CliRunner()
        return runner.invoke(
            services_group,
            args,
            obj={"adapter": adapter, "console": MagicMock()},
        )

    def test_up_calls_start_services(self) -> None:
        """up command calls adapter.start_services()."""
        adapter = _make_adapter()
        result = self._invoke(["up"], adapter)
        assert result.exit_code == 0
        adapter.start_services.assert_called_once()

    def test_down_calls_stop_services(self) -> None:
        """down command calls adapter.stop_services()."""
        adapter = _make_adapter()
        result = self._invoke(["down"], adapter)
        assert result.exit_code == 0
        adapter.stop_services.assert_called_once()

    def test_restart_calls_restart_with_service_name(self) -> None:
        """restart --service calls adapter.restart_services() with name."""
        adapter = _make_adapter()
        result = self._invoke(["restart", "--service", "api"], adapter)
        assert result.exit_code == 0
        adapter.restart_services.assert_called_once_with("api")

    def test_restart_calls_restart_with_none_when_no_service(self) -> None:
        """restart without --service calls adapter.restart_services(None)."""
        adapter = _make_adapter()
        result = self._invoke(["restart"], adapter)
        assert result.exit_code == 0
        adapter.restart_services.assert_called_once_with(None)
