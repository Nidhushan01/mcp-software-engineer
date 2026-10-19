"""Security helpers for repository filesystem access."""

from __future__ import annotations

from pathlib import Path

from .config import get_repository_root


class RepositoryAccessError(ValueError):
    """Raised when a requested path is outside the configured repository."""


def resolve_repository_path(path: str = ".", *, must_exist: bool = True) -> Path:
    """Resolve a user path and ensure it remains inside the repository root."""
    root = get_repository_root()
    requested = Path(path or ".")

    if requested.is_absolute():
        raise RepositoryAccessError("Absolute paths are not allowed")

    resolved = (root / requested).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RepositoryAccessError("Path escapes the configured repository root") from exc

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Repository path does not exist: {path}")

    return resolved


def repository_relative_path(path: Path) -> str:
    """Return a stable POSIX-style path relative to the repository root."""
    relative = path.resolve().relative_to(get_repository_root())
    return "." if not relative.parts else relative.as_posix()
