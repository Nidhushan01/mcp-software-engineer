"""Resource handlers for repository content."""

from __future__ import annotations

import json
from urllib.parse import unquote

from .tools import get_repository_structure, read_file


def repository_structure_resource() -> str:
    """Serialize the complete repository structure as formatted JSON."""
    return json.dumps(get_repository_structure(), indent=2)


def repository_file_resource(path: str) -> str:
    """Return the text content of a repository file resource."""
    return read_file(unquote(path))["content"]
