"""Path boundary for documentation access."""

from __future__ import annotations

from pathlib import Path

from .config import get_knowledge_root


class KnowledgeAccessError(ValueError):
    pass


def resolve_document_path(path: str) -> Path:
    requested = Path(path)
    if requested.is_absolute():
        raise KnowledgeAccessError("Absolute paths are not allowed")
    root = get_knowledge_root()
    resolved = (root / requested).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise KnowledgeAccessError("Path escapes the configured knowledge root") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Document does not exist: {path}")
    return resolved


def relative_document_path(path: Path) -> str:
    return path.resolve().relative_to(get_knowledge_root()).as_posix()
