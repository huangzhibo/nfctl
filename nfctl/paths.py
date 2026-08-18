"""CLI-side path normalization for server-visible launch directories."""

from pathlib import Path


def normalize_launch_dir(value: str) -> str:
    """Resolve relative input in the caller's cwd before crossing HTTP."""
    return str(Path(value).expanduser().resolve(strict=False))
