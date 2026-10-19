"""Write-capable MCP server; keep separate from the read-only Repository MCP."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

from mcp_servers.patch.tools import apply_patch as apply_patch_impl
from mcp_servers.patch.tools import generate_diff as generate_diff_impl
from mcp_servers.patch.tools import validate_patch as validate_patch_impl


mcp = MCPServer("patch", instructions="Propose and validate patches. Apply only after explicit human approval.")


@mcp.tool()
def generate_diff(path: str, new_content: str) -> dict[str, Any]:
    """Create an immutable unified-diff proposal without modifying the repository."""
    return generate_diff_impl(path, new_content)


@mcp.tool()
def validate_patch(proposal_id: str) -> dict[str, Any]:
    """Validate boundary, source hash, non-empty diff, and Python syntax without writing."""
    return validate_patch_impl(proposal_id)


@mcp.tool()
def apply_patch(proposal_id: str, approval: str) -> dict[str, Any]:
    """Apply a validated proposal only with the exact human approval phrase."""
    return apply_patch_impl(proposal_id, approval)


if __name__ == "__main__":
    mcp.run()
