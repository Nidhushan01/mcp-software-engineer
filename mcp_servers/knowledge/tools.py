"""Documentation retrieval and lightweight semantic search."""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import MAX_DOCUMENT_SIZE, MAX_RESULTS, SUPPORTED_EXTENSIONS, get_knowledge_root
from .security import relative_document_path, resolve_document_path
from .rag import get_rag


_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")


def _documents():
    root = get_knowledge_root()
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS and path.stat().st_size <= MAX_DOCUMENT_SIZE:
            yield path


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Document is not valid UTF-8: {relative_document_path(path)}") from exc


def _title(path: Path, content: str) -> str:
    for line in content.splitlines():
        if line.lstrip().startswith("#"):
            return line.lstrip("# ").strip()
    return path.stem.replace("-", " ").replace("_", " ").title()


def _tokens(text: str) -> Counter[str]:
    return Counter(token.casefold() for token in _TOKEN_RE.findall(text))


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    common = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in common)
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(sum(value * value for value in right.values()))
    return numerator / denominator if denominator else 0.0


def _snippet(lines: list[str], line: int, radius: int = 1) -> str:
    return "\n".join(lines[max(0, line - radius - 1): min(len(lines), line + radius)]).strip()


def search_docs(query: str) -> dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    for path in _documents():
        lines = _read(path).splitlines()
        for number, line in enumerate(lines, 1):
            if needle in line.casefold():
                matches.append({"path": relative_document_path(path), "line": number, "text": line.strip(), "snippet": _snippet(lines, number)})
                if len(matches) == MAX_RESULTS:
                    return {"query": query, "matches": matches, "count": len(matches), "truncated": True}
    return {"query": query, "matches": matches, "count": len(matches), "truncated": False}


def search_library_docs(library: str, query: str) -> dict[str, Any]:
    if not library.strip() or not query.strip():
        raise ValueError("Library and query cannot be empty")
    library_key = library.casefold()
    candidates = [path for path in _documents() if library_key in relative_document_path(path).casefold() or library_key in _read(path)[:1000].casefold()]
    matches: list[dict[str, Any]] = []
    for path in candidates:
        for number, line in enumerate(_read(path).splitlines(), 1):
            if query.casefold() in line.casefold():
                matches.append({"path": relative_document_path(path), "line": number, "text": line.strip()})
    return {"library": library, "query": query, "matches": matches[:MAX_RESULTS], "count": min(len(matches), MAX_RESULTS), "truncated": len(matches) > MAX_RESULTS}


def get_document(path: str) -> dict[str, Any]:
    document = resolve_document_path(path)
    content = _read(document)
    return {"path": relative_document_path(document), "title": _title(document, content), "size": document.stat().st_size, "content": content}


def get_api_reference(name: str) -> dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("API name cannot be empty")
    patterns = (f"`{name.casefold()}`", name.casefold())
    matches: list[dict[str, Any]] = []
    for path in _documents():
        lines = _read(path).splitlines()
        for number, line in enumerate(lines, 1):
            if any(pattern in line.casefold() for pattern in patterns):
                matches.append({"path": relative_document_path(path), "line": number, "reference": line.strip(), "context": _snippet(lines, number, 2)})
                if len(matches) == MAX_RESULTS:
                    break
    return {"name": name, "matches": matches, "count": len(matches)}


def semantic_search(query: str, limit: int = 10) -> dict[str, Any]:
    return get_rag().search(query, limit)


def refresh_index() -> dict[str, Any]:
    """Rebuild Qdrant candidates from current documentation and repository files."""
    return get_rag().refresh()


def find_related_documents(path: str, limit: int = 5) -> dict[str, Any]:
    if not 1 <= limit <= 25:
        raise ValueError("limit must be between 1 and 25")
    source = resolve_document_path(path)
    source_vector = _tokens(_read(source))
    matches = []
    for candidate in _documents():
        if candidate == source:
            continue
        content = _read(candidate)
        score = _cosine(source_vector, _tokens(content))
        if score > 0:
            matches.append({"path": relative_document_path(candidate), "title": _title(candidate, content), "score": round(score, 4)})
    matches.sort(key=lambda item: item["score"], reverse=True)
    return {"path": relative_document_path(source), "related": matches[:limit], "count": min(len(matches), limit)}
