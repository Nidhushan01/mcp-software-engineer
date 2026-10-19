"""Repository MCP server exposing safe, read-only codebase access."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

# ``mcp dev path/to/server.py`` imports this file directly instead of as the
# ``mcp_servers.repository.server`` package module. Add the project root so
# absolute package imports work in both launch modes.
if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from mcp_servers.repository.resources import (
    repository_file_resource,
    repository_structure_resource,
)
from mcp_servers.repository.dependency_tools import (
    find_dependency as find_dependency_impl,
    get_dependencies as get_dependencies_impl,
    get_dependency_version as get_dependency_version_impl,
)
from mcp_servers.repository.git_tools import (
    git_blame as git_blame_impl,
    git_diff as git_diff_impl,
    git_log as git_log_impl,
    git_show_commit as git_show_commit_impl,
    git_status as git_status_impl,
)
from mcp_servers.repository.tools import (
    find_files as find_files_impl,
    find_symbol as find_symbol_impl,
    get_file_metadata as get_file_metadata_impl,
    get_repository_structure as get_repository_structure_impl,
    list_directory as list_directory_impl,
    read_file as read_file_impl,
    search_code as search_code_impl,
    search_imports as search_imports_impl,
)


mcp = MCPServer(
    "repository",
    instructions="Read and search files inside the configured repository root.",
)


@mcp.tool()
def list_directory(path: str = ".") -> dict[str, Any]:
    """List entries in a repository directory."""
    return list_directory_impl(path)


@mcp.tool()
def read_file(path: str) -> dict[str, Any]:
    """Read a UTF-8 text file in the repository."""
    return read_file_impl(path)


@mcp.tool()
def search_code(query: str) -> dict[str, Any]:
    """Search all repository text files for a case-insensitive literal string."""
    return search_code_impl(query)


@mcp.tool()
def get_repository_structure() -> dict[str, Any]:
    """Return the full directory and file tree for the repository."""
    return get_repository_structure_impl()


@mcp.tool()
def get_file_metadata(path: str) -> dict[str, Any]:
    """Return size, modification time, extension, and SHA-256 for a file."""
    return get_file_metadata_impl(path)


@mcp.tool()
def find_files(pattern: str) -> dict[str, Any]:
    """Find repository files using a case-insensitive glob pattern."""
    return find_files_impl(pattern)


@mcp.tool()
def search_imports(module: str) -> dict[str, Any]:
    """Find Python files that import a module or one of its submodules."""
    return search_imports_impl(module)


@mcp.tool()
def find_symbol(name: str) -> dict[str, Any]:
    """Find Python classes, functions, and variables by exact name."""
    return find_symbol_impl(name)


@mcp.tool()
def git_status() -> dict[str, Any]:
    """Return the repository branch and working-tree status."""
    return git_status_impl()


@mcp.tool()
def git_log(limit: int = 20) -> dict[str, Any]:
    """Return recent commits, newest first (limit 1-100)."""
    return git_log_impl(limit)


@mcp.tool()
def git_diff(commit: str | None = None) -> dict[str, Any]:
    """Return the working-tree diff, optionally relative to a commit."""
    return git_diff_impl(commit)


@mcp.tool()
def git_show_commit(commit: str) -> dict[str, Any]:
    """Return metadata and patch for one commit identifier."""
    return git_show_commit_impl(commit)


@mcp.tool()
def git_blame(path: str) -> dict[str, Any]:
    """Return line-by-line Git attribution for a repository file."""
    return git_blame_impl(path)


@mcp.tool()
def get_dependencies() -> dict[str, Any]:
    """Read supported dependency manifests and return declared dependencies."""
    return get_dependencies_impl()


@mcp.tool()
def find_dependency(name: str) -> dict[str, Any]:
    """Find a declared dependency by case-insensitive exact name."""
    return find_dependency_impl(name)


@mcp.tool()
def get_dependency_version(name: str) -> dict[str, Any]:
    """Return all declared version constraints for a dependency."""
    return get_dependency_version_impl(name)


@mcp.resource("repo://structure", mime_type="application/json")
def repository_structure() -> str:
    """Return the repository tree as JSON."""
    return repository_structure_resource()


@mcp.resource("repo://file/{+path}", mime_type="text/plain")
def repository_file(path: str) -> str:
    """Return a repository file by its relative path."""
    return repository_file_resource(path)


if __name__ == "__main__":
    mcp.run()
