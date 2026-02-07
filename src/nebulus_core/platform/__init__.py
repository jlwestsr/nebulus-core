"""Platform detection and adapter system."""

from nebulus_core.platform.base import PlatformAdapter, ServiceInfo
from nebulus_core.platform.detection import detect_platform
from nebulus_core.platform.registry import adapter_available, load_adapter

__all__ = [
    "PlatformAdapter",
    "ServiceInfo",
    "adapter_available",
    "detect_platform",
    "load_adapter",
]
