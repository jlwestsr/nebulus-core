"""Adapter discovery and registration via entry points."""

import sys

if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    from importlib.metadata import entry_points

from nebulus_core.platform.base import PlatformAdapter


def load_adapter(platform_name: str) -> PlatformAdapter:
    """Load a platform adapter by name via entry points.

    Platform projects register their adapter in pyproject.toml:

        [project.entry-points."nebulus.platform"]
        prime = "nebulus_prime.adapter:PrimeAdapter"

    Args:
        platform_name: The platform identifier ('prime' or 'edge').

    Returns:
        An instantiated PlatformAdapter.

    Raises:
        RuntimeError: If no adapter is found for the platform.
    """
    eps = entry_points(group="nebulus.platform")
    for ep in eps:
        if ep.name == platform_name:
            adapter_cls = ep.load()
            return adapter_cls()

    raise RuntimeError(
        f"No adapter found for platform: {platform_name}. "
        f"Install the corresponding package (nebulus-prime or nebulus-edge)."
    )
