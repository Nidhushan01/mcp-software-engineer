"""Qdrant-backed retrieval with source-rich payload metadata."""

from __future__ import annotations

import ast
import atexit
import hashlib
import math
import os
import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from qdrant_client import QdrantClient, models

from .config import PROJECT_ROOT, SUPPORTED_EXTENSIONS, get_knowledge_root


COLLECTION = os.getenv("QDRANT_COLLECTION", "software_engineer_knowledge")
VECTOR_SIZE = 384
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")
_LANGUAGES = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript", ".java": "java", ".go": "go", ".rs": "rust", ".md": "markdown", ".rst": "rst", ".txt": "text"}
_IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}
_OPEN_CLIENTS: list[QdrantClient] = []


class HashingEmbedder:
    """Deterministic local feature hashing; replaceable without changing payloads."""

    size = VECTOR_SIZE

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        for token in _TOKEN_RE.findall(text.casefold()):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "big")
            vector[number % self.size] += 1.0 if number & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector


def _repository_root() -> Path | None:
    configured = os.getenv("REPOSITORY_ROOT")
    if not configured:
        return None
    root = Path(configured).resolve()
    return root if root.is_dir() else None


def _client() -> QdrantClient:
    url = os.getenv("QDRANT_URL")
    if url:
        client = QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY"))
        _OPEN_CLIENTS.append(client)
        return client
    path = os.getenv("QDRANT_PATH", str(PROJECT_ROOT / ".qdrant_data"))
    client = QdrantClient(location=":memory:") if path == ":memory:" else QdrantClient(path=path)
    _OPEN_CLIENTS.append(client)
    return client


def close_rag_clients() -> None:
    """Release embedded SQLite handles (especially important on Windows)."""
    _configured_rag.cache_clear()
    while _OPEN_CLIENTS:
        _OPEN_CLIENTS.pop().close()


def _payload(source: str, path: str, language: str, text: str, start: int, end: int, symbol: str | None = None) -> dict[str, Any]:
    return {
        "source": source,
        "path": path,
        "language": language,
        "symbol": symbol,
        "start_line": start,
        "end_line": end,
        "text": text,
        "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def _documentation_chunks() -> Iterable[dict[str, Any]]:
    root = get_knowledge_root()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        relative = path.relative_to(root).as_posix()
        start = 1
        buffer: list[str] = []
        for number, line in enumerate(lines, 1):
            if line.startswith("#") and buffer:
                text = "\n".join(buffer).strip()
                if text:
                    yield _payload("documentation", relative, _LANGUAGES.get(path.suffix.casefold(), "text"), text, start, number - 1)
                buffer, start = [], number
            buffer.append(line)
        text = "\n".join(buffer).strip()
        if text:
            yield _payload("documentation", relative, _LANGUAGES.get(path.suffix.casefold(), "text"), text, start, len(lines))


def _python_chunks(path: Path, relative: str, content: str) -> Iterable[dict[str, Any]]:
    lines = content.splitlines()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return
    yielded = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            start, end = node.lineno, getattr(node, "end_lineno", node.lineno)
            text = "\n".join(lines[start - 1:end])
            yielded = True
            yield _payload("repository", relative, "python", text, start, end, node.name)
    if not yielded and content.strip():
        yield _payload("repository", relative, "python", content, 1, len(lines))


def _repository_chunks() -> Iterable[dict[str, Any]]:
    root = _repository_root()
    if root is None:
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in _IGNORED for part in path.parts):
            continue
        language = _LANGUAGES.get(path.suffix.casefold())
        if not language:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        relative = path.relative_to(root).as_posix()
        if language == "python":
            yield from _python_chunks(path, relative, content)
        elif content.strip():
            lines = content.splitlines()
            for offset in range(0, len(lines), 35):
                block = lines[offset: offset + 40]
                yield _payload("repository", relative, language, "\n".join(block), offset + 1, offset + len(block))


class QdrantRAG:
    def __init__(self, client: QdrantClient | None = None, embedder: HashingEmbedder | None = None) -> None:
        self.client = client or _client()
        self.embedder = embedder or HashingEmbedder()

    def refresh(self) -> dict[str, Any]:
        if self.client.collection_exists(COLLECTION):
            self.client.delete_collection(COLLECTION)
        self.client.create_collection(
            collection_name=COLLECTION,
            vectors_config=models.VectorParams(size=self.embedder.size, distance=models.Distance.COSINE),
        )
        chunks = list(_documentation_chunks()) + list(_repository_chunks())
        points = []
        for payload in chunks:
            identity = f"{payload['source']}:{payload['path']}:{payload['start_line']}:{payload['end_line']}:{payload['content_sha256']}"
            points.append(models.PointStruct(id=str(uuid.uuid5(uuid.NAMESPACE_URL, identity)), vector=self.embedder.embed(payload["text"]), payload=payload))
        if points:
            self.client.upsert(collection_name=COLLECTION, points=points, wait=True)
        sources = CounterLike(payload["source"] for payload in chunks)
        return {"collection": COLLECTION, "chunks": len(chunks), "sources": dict(sources)}

    def ensure_index(self) -> None:
        if not self.client.collection_exists(COLLECTION):
            self.refresh()

    def search(self, query: str, limit: int = 10, source: str | None = None) -> dict[str, Any]:
        if not query.strip():
            raise ValueError("Query cannot be empty")
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        self.ensure_index()
        query_filter = None
        if source:
            query_filter = models.Filter(must=[models.FieldCondition(key="source", match=models.MatchValue(value=source))])
        response = self.client.query_points(
            collection_name=COLLECTION,
            query=self.embedder.embed(query),
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        matches = []
        for point in response.points:
            payload = dict(point.payload or {})
            payload["score"] = round(float(point.score), 4)
            matches.append(payload)
        return {"query": query, "matches": matches, "count": len(matches), "backend": "qdrant"}


@lru_cache(maxsize=8)
def _configured_rag(url: str, path: str, api_key: str, knowledge_root: str, repository_root: str) -> QdrantRAG:
    """Reuse local clients so embedded Qdrant storage is not opened twice."""
    return QdrantRAG()


def get_rag() -> QdrantRAG:
    return _configured_rag(
        os.getenv("QDRANT_URL", ""),
        os.getenv("QDRANT_PATH", str(PROJECT_ROOT / ".qdrant_data")),
        os.getenv("QDRANT_API_KEY", ""),
        os.getenv("KNOWLEDGE_ROOT", ""),
        os.getenv("REPOSITORY_ROOT", ""),
    )


class CounterLike(dict[str, int]):
    def __init__(self, values: Iterable[str]) -> None:
        super().__init__()
        for value in values:
            self[value] = self.get(value, 0) + 1


atexit.register(close_rag_clients)
