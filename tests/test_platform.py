"""Tests for platform detection and adapter system."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from nebulus_core.platform.base import PlatformAdapter, ServiceInfo
from nebulus_core.platform.detection import detect_platform


class TestPlatformDetection:
    """Tests for auto-detection logic."""

    def test_env_override_prime(self) -> None:
        """NEBULUS_PLATFORM=prime should override detection."""
        with patch.dict(os.environ, {"NEBULUS_PLATFORM": "prime"}):
            assert detect_platform() == "prime"

    def test_env_override_edge(self) -> None:
        """NEBULUS_PLATFORM=edge should override detection."""
        with patch.dict(os.environ, {"NEBULUS_PLATFORM": "edge"}):
            assert detect_platform() == "edge"

    def test_env_override_invalid(self) -> None:
        """Invalid NEBULUS_PLATFORM value should raise."""
        with patch.dict(os.environ, {"NEBULUS_PLATFORM": "invalid"}):
            with pytest.raises(RuntimeError, match="Invalid NEBULUS_PLATFORM"):
                detect_platform()

    @patch("nebulus_core.platform.detection.platform_mod.system", return_value="Linux")
    def test_linux_detected_as_prime(self, mock_system: object) -> None:
        """Linux should auto-detect as prime."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEBULUS_PLATFORM", None)
            assert detect_platform() == "prime"

    @patch("nebulus_core.platform.detection.platform_mod.machine", return_value="arm64")
    @patch("nebulus_core.platform.detection.platform_mod.system", return_value="Darwin")
    def test_macos_arm64_detected_as_edge(
        self, mock_system: object, mock_machine: object
    ) -> None:
        """macOS ARM64 should auto-detect as edge."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEBULUS_PLATFORM", None)
            assert detect_platform() == "edge"

    @patch(
        "nebulus_core.platform.detection.platform_mod.system", return_value="Windows"
    )
    def test_unsupported_platform_raises(self, mock_system: object) -> None:
        """Unsupported platforms should raise RuntimeError."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NEBULUS_PLATFORM", None)
            with pytest.raises(RuntimeError, match="Unsupported platform"):
                detect_platform()


class TestServiceInfo:
    """Tests for the ServiceInfo model."""

    def test_service_info_creation(self) -> None:
        """ServiceInfo should accept valid data."""
        svc = ServiceInfo(
            name="tabby",
            port=5000,
            health_endpoint="http://localhost:5000/v1/models",
            description="LLM inference",
        )
        assert svc.name == "tabby"
        assert svc.port == 5000


class TestMockAdapterProtocol:
    """Verify mock adapter satisfies the protocol."""

    def test_mock_adapter_is_platform_adapter(self, mock_adapter: object) -> None:
        """MockAdapter should satisfy PlatformAdapter protocol."""
        assert isinstance(mock_adapter, PlatformAdapter)


def test_adapter_has_default_model(mock_adapter):
    """Adapter must expose a default model name."""
    assert isinstance(mock_adapter.default_model, str)
    assert len(mock_adapter.default_model) > 0


def test_adapter_has_data_dir(mock_adapter):
    """Adapter must expose a data directory path."""
    assert isinstance(mock_adapter.data_dir, Path)
