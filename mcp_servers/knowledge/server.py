"""Knowledge MCP server exposing read-only documentation retrieval."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from mcp.server import MCPServer

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from mcp_servers.knowledge.tools import (
    find_related_documents as find_related_documents_impl,
    get_api_reference as get_api_reference_impl,
    get_document as get_document_impl,
    search_docs as search_docs_impl,
    search_library_docs as search_library_docs_impl,
    semantic_search as semantic_search_impl,
    refresh_index as refresh_index_impl,
)


mcp = MCPServer("knowledge", instructions="Search and read technical documentation inside the configured knowledge root.")


@mcp.tool()
def search_docs(query: str) -> dict[str, Any]:
    """Search documentation for a case-insensitive literal string."""
    return search_docs_impl(query)


@mcp.tool()
def search_library_docs(library: str, query: str) -> dict[str, Any]:
    """Search documentation associated with a library or dependency."""
    return search_library_docs_impl(library, query)


@mcp.tool()
def get_document(path: str) -> dict[str, Any]:
    """Read one UTF-8 document and return its metadata and content."""
    return get_document_impl(path)


@mcp.tool()
def get_api_reference(name: str) -> dict[str, Any]:
    """Find documentation sections mentioning an API, symbol, or endpoint."""
    return get_api_reference_impl(name)


@mcp.tool()
def semantic_search(query: str, limit: int = 10) -> dict[str, Any]:
    """Find repository and documentation candidates through Qdrant."""
    return semantic_search_impl(query, limit)


@mcp.tool()
def refresh_index() -> dict[str, Any]:
    """Rebuild the Qdrant index from current documentation and repository files."""
    return refresh_index_impl()


@mcp.tool()
def find_related_documents(path: str, limit: int = 5) -> dict[str, Any]:
    """Find documents semantically related to another document."""
    return find_related_documents_impl(path, limit)


@mcp.resource("knowledge://document/{+path}", mime_type="text/markdown")
def document_resource(path: str) -> str:
    return get_document_impl(unquote(path))["content"]


if __name__ == "__main__":
    mcp.run()
