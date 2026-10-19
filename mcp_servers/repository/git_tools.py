"""Read-only Git operations scoped to the configured repository."""

from __future__ import annotations

import subprocess
import re
from typing import Any

from .config import GIT_COMMAND_TIMEOUT_SECONDS
from .security import repository_relative_path, resolve_repository_path


def _git(*args: str) -> str:
    root = resolve_repository_path(".")
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Git is not installed or is not available on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Git command timed out") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Git command failed")
    return result.stdout


def git_status() -> dict[str, Any]:
    output = _git("status", "--short", "--branch")
    lines = output.splitlines()
    return {"branch": lines[0][3:] if lines and lines[0].startswith("## ") else None, "changes": lines[1:] if lines else [], "clean": len(lines) <= 1}


def git_log(limit: int = 20) -> dict[str, Any]:
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    output = _git("log", f"-{limit}", "--date=iso-strict", "--pretty=format:%H%x1f%an%x1f%ad%x1f%s")
    commits = []
    for line in output.splitlines():
        commit, author, date, subject = line.split("\x1f", 3)
        commits.append({"commit": commit, "author": author, "date": date, "subject": subject})
    return {"commits": commits, "count": len(commits)}


def git_diff(commit: str | None = None) -> dict[str, Any]:
    if commit is not None and not _valid_revision(commit):
        raise ValueError("A valid commit identifier is required")
    args = ["diff", "--no-ext-diff", "--"] if commit is None else ["diff", "--no-ext-diff", commit, "--"]
    output = _git(*args)
    return {"base": commit, "diff": output, "empty": not bool(output)}


def git_show_commit(commit: str) -> dict[str, Any]:
    if not _valid_revision(commit):
        raise ValueError("A valid commit identifier is required")
    output = _git("show", "--no-ext-diff", "--format=fuller", "--stat", "--patch", commit, "--")
    return {"commit": commit, "content": output}


def git_blame(path: str) -> dict[str, Any]:
    file_path = resolve_repository_path(path)
    if not file_path.is_file():
        raise IsADirectoryError(f"Not a file: {path}")
    relative = repository_relative_path(file_path)
    return {"path": relative, "blame": _git("blame", "--date=iso-strict", "--", relative)}


def _valid_revision(revision: str) -> bool:
    """Allow ordinary hashes/ref expressions while preventing option injection."""
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/~^{}-]*", revision or ""))
