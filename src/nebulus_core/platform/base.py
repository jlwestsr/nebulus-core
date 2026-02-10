"""Platform adapter protocol and service info model."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ServiceInfo(BaseModel):
    """Describes a managed service."""

    name: str
    port: int
    health_endpoint: str
    description: str


@runtime_checkable
class PlatformAdapter(Protocol):
    """Interface that each platform project implements.

    Platform projects (nebulus-prime, nebulus-edge) provide a concrete
    class implementing this protocol and register it via entry points.
    """

    @property
    def platform_name(self) -> str:
        """Platform identifier, e.g. 'prime' or 'edge'."""
        ...

    @property
    def services(self) -> list[ServiceInfo]:
        """All services managed by this platform."""
        ...

    @property
    def llm_base_url(self) -> str:
        """OpenAI-compatible endpoint base URL."""
        ...

    @property
    def chroma_settings(self) -> dict:
        """ChromaDB connection config.

        Returns:
            For HTTP mode: {"mode": "http", "host": str, "port": int}
            For embedded mode: {"mode": "embedded", "path": str}
        """
        ...

    @property
    def default_model(self) -> str:
        """Default LLM model name for this platform."""
        ...

    @property
    def data_dir(self) -> Path:
        """Root directory for persistent data (graph, cache, etc.)."""
        ...

    def start_services(self) -> None:
        """Start all platform services."""
        ...

    def stop_services(self) -> None:
        """Stop all platform services."""
        ...

    def restart_services(self, service: str | None = None) -> None:
        """Restart one or all services.

        Args:
            service: Specific service name, or None for all.
        """
        ...

    def get_logs(self, service: str, follow: bool = False) -> None:
        """Stream logs for a service.

        Args:
            service: Service name to get logs for.
            follow: Whether to follow/tail the log output.
        """
        ...

    @property
    def mcp_settings(self) -> dict:
        """MCP server configuration overrides.

        Returns:
            Dict with optional keys: workspace_path, allowed_commands,
            server_name.
        """
        ...

    def platform_specific_commands(self) -> list:
        """Return additional Click commands for this platform."""
        ...
