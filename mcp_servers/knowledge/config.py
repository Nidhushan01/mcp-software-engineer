"""Knowledge-base configuration."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge_base"
SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}
MAX_DOCUMENT_SIZE = int(os.getenv("KNOWLEDGE_MAX_DOCUMENT_SIZE", "1000000"))
MAX_RESULTS = int(os.getenv("KNOWLEDGE_MAX_RESULTS", "50"))


def get_knowledge_root() -> Path:
    configured = os.getenv("KNOWLEDGE_ROOT")
    root = Path(configured).expanduser() if configured else DEFAULT_KNOWLEDGE_ROOT
    root = root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"Knowledge root is not a directory: {root}")
    return root
