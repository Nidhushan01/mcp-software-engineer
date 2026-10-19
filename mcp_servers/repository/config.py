"""Configuration for the repository MCP server."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPOSITORY_ROOT = PROJECT_ROOT / "sample_repos" / "vulnerable-fastapi-app"


def get_repository_root() -> Path:
    """Return the configured repository root as an absolute path."""
    configured_root = os.getenv("REPOSITORY_ROOT")
    root = Path(configured_root).expanduser() if configured_root else DEFAULT_REPOSITORY_ROOT
    root = root.resolve()

    if not root.exists():
        raise RuntimeError(f"Repository root does not exist: {root}")
    if not root.is_dir():
        raise RuntimeError(f"Repository root is not a directory: {root}")

    return root


MAX_FILE_SIZE_BYTES = int(os.getenv("REPOSITORY_MAX_FILE_SIZE", "1000000"))
MAX_SEARCH_RESULTS = int(os.getenv("REPOSITORY_MAX_SEARCH_RESULTS", "100"))
GIT_COMMAND_TIMEOUT_SECONDS = int(os.getenv("REPOSITORY_GIT_TIMEOUT", "10"))

IGNORED_DIRECTORIES = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "venv",
}
