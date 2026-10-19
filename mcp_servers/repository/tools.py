"""Filesystem operations exposed as repository MCP tools."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import (
    GIT_COMMAND_TIMEOUT_SECONDS,
    IGNORED_DIRECTORIES,
    MAX_FILE_SIZE_BYTES,
    MAX_SEARCH_RESULTS,
)
from .security import repository_relative_path, resolve_repository_path


def _entry(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": path.name,
        "path": repository_relative_path(path),
        "type": "directory" if path.is_dir() else "file",
    }
    if path.is_file():
        result["size"] = path.stat().st_size
    return result


def list_directory(path: str = ".") -> dict[str, Any]:
    """List the immediate files and directories at a repository-relative path."""
    directory = resolve_repository_path(path)
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
    return {
        "path": repository_relative_path(directory),
        "entries": [_entry(item) for item in entries],
    }


def read_file(path: str) -> dict[str, Any]:
    """Read a UTF-8 text file from a repository-relative path."""
    file_path = resolve_repository_path(path)
    if not file_path.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    size = file_path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File is too large ({size} bytes); limit is {MAX_FILE_SIZE_BYTES} bytes"
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"File is not valid UTF-8 text: {path}") from exc

    return {
        "path": repository_relative_path(file_path),
        "size": size,
        "content": content,
    }


def get_file_metadata(path: str) -> dict[str, Any]:
    """Return safe metadata for one repository file without reading its content."""
    file_path = resolve_repository_path(path)
    if not file_path.is_file():
        raise IsADirectoryError(f"Not a file: {path}")

    stat = file_path.stat()
    digest = hashlib.sha256()
    with file_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    return {
        "path": repository_relative_path(file_path),
        "name": file_path.name,
        "extension": file_path.suffix,
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": digest.hexdigest(),
    }


def _walk_files(root: Path):
    for item in sorted(root.rglob("*")):
        if any(part in IGNORED_DIRECTORIES for part in item.parts):
            continue
        if item.is_file():
            yield item


def search_code(query: str) -> dict[str, Any]:
    """Search repository text files for a case-insensitive literal string."""
    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    root = resolve_repository_path(".")
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    truncated = False

    for file_path in _walk_files(root):
        if file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if needle in line.casefold():
                if len(matches) == MAX_SEARCH_RESULTS:
                    truncated = True
                    break
                matches.append(
                    {
                        "path": repository_relative_path(file_path),
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
        if truncated:
            break

    return {
        "query": query,
        "matches": matches,
        "count": len(matches),
        "truncated": truncated,
    }


def find_files(pattern: str) -> dict[str, Any]:
    """Find files by a case-insensitive glob matched against name and relative path."""
    if not pattern or not pattern.strip():
        raise ValueError("File pattern cannot be empty")
    normalized = pattern.replace("\\", "/").casefold()
    matches: list[dict[str, Any]] = []
    truncated = False
    for file_path in _walk_files(resolve_repository_path(".")):
        relative = repository_relative_path(file_path)
        if fnmatch.fnmatch(relative.casefold(), normalized) or fnmatch.fnmatch(
            file_path.name.casefold(), normalized
        ):
            if len(matches) == MAX_SEARCH_RESULTS:
                truncated = True
                break
            matches.append(_entry(file_path))
    return {"pattern": pattern, "matches": matches, "count": len(matches), "truncated": truncated}


_IMPORT_RE = re.compile(
    r"^\s*(?:from\s+([\w.]+)\s+import\s+|import\s+([^#]+))", re.MULTILINE
)


def search_imports(module: str) -> dict[str, Any]:
    """Find Python import statements that refer to a module or its submodules."""
    if not module or not module.strip():
        raise ValueError("Module cannot be empty")
    target = module.strip().casefold()
    matches: list[dict[str, Any]] = []
    for file_path in _walk_files(resolve_repository_path(".")):
        if file_path.suffix != ".py" or file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(lines, 1):
            match = _IMPORT_RE.match(line)
            if not match:
                continue
            imported = match.group(1) or match.group(2) or ""
            names = [part.strip().split(" as ", 1)[0].casefold() for part in imported.split(",")]
            if any(name == target or name.startswith(target + ".") for name in names):
                matches.append({"path": repository_relative_path(file_path), "line": line_number, "text": line.strip()})
                if len(matches) == MAX_SEARCH_RESULTS:
                    return {"module": module, "matches": matches, "count": len(matches), "truncated": True}
    return {"module": module, "matches": matches, "count": len(matches), "truncated": False}


def find_symbol(name: str) -> dict[str, Any]:
    """Find Python class, function, async-function, and assignment definitions."""
    if not name or not name.strip():
        raise ValueError("Symbol name cannot be empty")
    target = name.strip()
    matches: list[dict[str, Any]] = []
    for file_path in _walk_files(resolve_repository_path(".")):
        if file_path.suffix != ".py" or file_path.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (UnicodeDecodeError, OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            symbol_name: str | None = None
            kind: str | None = None
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol_name, kind = node.name, "function"
            elif isinstance(node, ast.ClassDef):
                symbol_name, kind = node.name, "class"
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(item, ast.Name) and item.id == target for item in targets):
                    symbol_name, kind = target, "variable"
            if symbol_name == target:
                matches.append({"path": repository_relative_path(file_path), "line": node.lineno, "kind": kind, "name": target})
                if len(matches) == MAX_SEARCH_RESULTS:
                    return {"name": name, "matches": matches, "count": len(matches), "truncated": True}
    return {"name": name, "matches": matches, "count": len(matches), "truncated": False}


def get_repository_structure() -> dict[str, Any]:
    """Return a recursive tree describing the configured repository."""
    root = resolve_repository_path(".")

    def build_tree(directory: Path) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = []
        items = sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        for item in items:
            if item.is_dir() and item.name in IGNORED_DIRECTORIES:
                continue
            node = _entry(item)
            if item.is_dir():
                node["children"] = build_tree(item)
            children.append(node)
        return children

    return {
        "name": root.name,
        "path": ".",
        "type": "directory",
        "children": build_tree(root),
    }
