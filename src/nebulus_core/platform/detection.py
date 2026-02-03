"""Auto-detect the current platform based on OS and hardware."""

import os
import platform as platform_mod


def detect_platform() -> str:
    """Detect which Nebulus platform to use.

    Checks the NEBULUS_PLATFORM environment variable first for explicit
    override, then falls back to OS/hardware detection.

    Returns:
        Platform identifier: 'prime' (Linux) or 'edge' (macOS ARM).

    Raises:
        RuntimeError: If the platform is unsupported.
    """
    override = os.environ.get("NEBULUS_PLATFORM")
    if override:
        if override in ("prime", "edge"):
            return override
        raise RuntimeError(
            f"Invalid NEBULUS_PLATFORM value: {override}. " "Must be 'prime' or 'edge'."
        )

    system = platform_mod.system()
    if system == "Linux":
        return "prime"
    elif system == "Darwin":
        machine = platform_mod.machine()
        if machine == "arm64":
            return "edge"
        raise RuntimeError(
            f"Unsupported macOS architecture: {machine}. "
            "Nebulus Edge requires Apple Silicon (arm64)."
        )
    else:
        raise RuntimeError(
            f"Unsupported platform: {system}. "
            "Nebulus supports Linux (Prime) and macOS ARM (Edge)."
        )
