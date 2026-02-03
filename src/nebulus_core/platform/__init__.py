"""Platform detection and adapter system."""

from nebulus_core.platform.base import PlatformAdapter, ServiceInfo
from nebulus_core.platform.detection import detect_platform
from nebulus_core.platform.registry import load_adapter

__all__ = [
    "PlatformAdapter",
    "ServiceInfo",
    "detect_platform",
    "load_adapter",
]
