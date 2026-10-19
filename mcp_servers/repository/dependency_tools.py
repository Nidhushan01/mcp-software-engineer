"""Dependency manifest discovery and parsing."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .security import repository_relative_path, resolve_repository_path

_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(.*)$")


def _add(result: list[dict[str, Any]], name: str, version: str, source: Path, group: str = "runtime") -> None:
    result.append({"name": name, "version": version or None, "source": repository_relative_path(source), "group": group})


def _parse_requirements(path: Path, result: list[dict[str, Any]]) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        match = _REQ_RE.match(line)
        if match:
            _add(result, match.group(1), match.group(2).strip(), path)


def _parse_pyproject(path: Path, result: list[dict[str, Any]]) -> None:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    for item in data.get("project", {}).get("dependencies", []):
        match = _REQ_RE.match(item)
        if match:
            _add(result, match.group(1), match.group(2).strip(), path)
    for group, items in data.get("project", {}).get("optional-dependencies", {}).items():
        for item in items:
            match = _REQ_RE.match(item)
            if match:
                _add(result, match.group(1), match.group(2).strip(), path, group)


def _parse_package_json(path: Path, result: list[dict[str, Any]]) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for section, group in (("dependencies", "runtime"), ("devDependencies", "development"), ("peerDependencies", "peer")):
        for name, version in data.get(section, {}).items():
            _add(result, name, str(version), path, group)


def get_dependencies() -> dict[str, Any]:
    root = resolve_repository_path(".")
    dependencies: list[dict[str, Any]] = []
    manifests: list[str] = []
    for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "package.json"):
        for path in root.rglob(name):
            if any(part in {".git", ".venv", "node_modules", "venv"} for part in path.parts):
                continue
            try:
                if name.startswith("requirements"):
                    _parse_requirements(path, dependencies)
                elif name == "pyproject.toml":
                    _parse_pyproject(path, dependencies)
                else:
                    _parse_package_json(path, dependencies)
                manifests.append(repository_relative_path(path))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
                raise ValueError(f"Cannot parse dependency manifest {repository_relative_path(path)}: {exc}") from exc
    return {"dependencies": dependencies, "count": len(dependencies), "manifests": manifests}


def find_dependency(name: str) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Dependency name cannot be empty")
    all_dependencies = get_dependencies()
    matches = [item for item in all_dependencies["dependencies"] if item["name"].casefold() == name.strip().casefold()]
    return {"name": name, "matches": matches, "count": len(matches)}


def get_dependency_version(name: str) -> dict[str, Any]:
    result = find_dependency(name)
    return {"name": name, "versions": sorted({item["version"] for item in result["matches"] if item["version"]}), "matches": result["matches"]}
