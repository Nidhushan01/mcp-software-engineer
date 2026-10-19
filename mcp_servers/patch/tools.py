"""Generate, validate, and explicitly apply repository patch proposals."""

from __future__ import annotations

import ast
import difflib
import hashlib
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp_servers.repository.security import repository_relative_path, resolve_repository_path
from mcp_servers.repository.config import get_repository_root


@dataclass
class Proposal:
    id: str
    repository_root: str
    path: str
    original_sha256: str
    new_content: str
    diff: str


_PROPOSALS: dict[str, Proposal] = {}


def _sha(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def generate_diff(path: str, new_content: str) -> dict[str, Any]:
    target = resolve_repository_path(path)
    if not target.is_file():
        raise ValueError("Patch target must be a file")
    original = target.read_text(encoding="utf-8")
    relative = repository_relative_path(target)
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{relative}",
        tofile=f"b/{relative}",
    ))
    if not diff:
        raise ValueError("Proposed content does not change the file")
    proposal_id = uuid.uuid4().hex
    proposal = Proposal(proposal_id, str(get_repository_root()), relative, _sha(original), new_content, diff)
    _PROPOSALS[proposal_id] = proposal
    return {"proposal_id": proposal_id, "path": relative, "diff": diff, "status": "proposed"}


def validate_patch(proposal_id: str) -> dict[str, Any]:
    proposal = _PROPOSALS.get(proposal_id)
    if proposal is None:
        raise ValueError("Unknown or expired patch proposal")
    if str(get_repository_root()) != proposal.repository_root:
        raise PermissionError("Patch proposal belongs to a different repository root")
    target = resolve_repository_path(proposal.path)
    current = target.read_text(encoding="utf-8")
    checks = {
        "inside_repository": True,
        "source_unchanged": _sha(current) == proposal.original_sha256,
        "non_empty_diff": bool(proposal.diff.strip()),
        "syntax_valid": True,
    }
    error = None
    if target.suffix.casefold() == ".py":
        try:
            ast.parse(proposal.new_content, filename=proposal.path)
        except SyntaxError as exc:
            checks["syntax_valid"] = False
            error = f"{exc.msg} at line {exc.lineno}"
    valid = all(checks.values())
    return {"proposal_id": proposal.id, "path": proposal.path, "valid": valid, "checks": checks, "error": error, "diff": proposal.diff}


def apply_patch(proposal_id: str, approval: str) -> dict[str, Any]:
    proposal = _PROPOSALS.get(proposal_id)
    if proposal is None:
        raise ValueError("Unknown or expired patch proposal")
    expected = f"APPROVE {proposal_id}"
    if approval != expected:
        raise PermissionError(f"Explicit approval required: {expected}")
    validation = validate_patch(proposal_id)
    if not validation["valid"]:
        raise ValueError("Patch is invalid or stale and cannot be applied")
    target = resolve_repository_path(proposal.path)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".patch", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(proposal.new_content)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    del _PROPOSALS[proposal_id]
    return {"proposal_id": proposal_id, "path": proposal.path, "status": "applied", "sha256": _sha(proposal.new_content)}
