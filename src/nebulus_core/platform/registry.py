"""Adapter discovery and registration via entry points."""

import sys

if sys.version_info >= (3, 12):
    from importlib.metadata import entry_points
else:
    from importlib.metadata import entry_points

from nebulus_core.platform.base import PlatformAdapter


def adapter_available(platform_name: str) -> bool:
    """Check if an adapter is registered for the given platform.

    Args:
        platform_name: The platform identifier ('prime' or 'edge').

    Returns:
        True if an adapter entry point exists, False otherwise.
    """
    eps = entry_points(group="nebulus.platform")
    return any(ep.name == platform_name for ep in eps)


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
    available = [ep.name for ep in eps]

    for ep in eps:
        if ep.name == platform_name:
            try:
                adapter_cls = ep.load()
            except Exception as exc:
                raise RuntimeError(
                    f"Adapter '{platform_name}' found but failed to import: {exc}. "
                    f"Check that the package is installed correctly."
                ) from exc
            return adapter_cls()

    available_str = ", ".join(available) if available else "none"
    raise RuntimeError(
        f"No adapter found for platform: {platform_name}. "
        f"Available adapters: [{available_str}]. "
        f"Install the corresponding package (nebulus-prime or nebulus-edge)."
    )
