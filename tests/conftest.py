"""Shared test configuration and fixtures."""

from pathlib import Path

import pytest

from nebulus_core.platform.base import ServiceInfo


class MockAdapter:
    """Test adapter for unit testing without a real platform."""

    @property
    def platform_name(self) -> str:
        return "test"

    @property
    def services(self) -> list[ServiceInfo]:
        return [
            ServiceInfo(
                name="test-service",
                port=9999,
                health_endpoint="http://localhost:9999/health",
                description="Test service",
            ),
        ]

    @property
    def llm_base_url(self) -> str:
        return "http://localhost:9999/v1"

    @property
    def chroma_settings(self) -> dict:
        return {"mode": "embedded", "path": "/tmp/test-chroma"}

    @property
    def default_model(self) -> str:
        return "test-model"

    @property
    def data_dir(self) -> Path:
        return Path("/tmp/test-nebulus-data")

    def start_services(self) -> None:
        pass

    def stop_services(self) -> None:
        pass

    def restart_services(self, service: str | None = None) -> None:
        pass

    def get_logs(self, service: str, follow: bool = False) -> None:
        pass

    @property
    def mcp_settings(self) -> dict:
        return {}

    def platform_specific_commands(self) -> list:
        return []


@pytest.fixture
def mock_adapter() -> MockAdapter:
    """Provide a mock platform adapter for tests."""
    return MockAdapter()
