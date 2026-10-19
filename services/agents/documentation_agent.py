"""Technical/internal documentation specialist backed by Knowledge MCP."""

from __future__ import annotations

from typing import Any

from mcp_clients.manager import MCPManager
from services.investigation.evidence import EvidenceStore, SourceType

from .state import AgentState


class DocumentationAgent:
    def __init__(self, manager: MCPManager, server_name: str = "knowledge") -> None:
        self.manager = manager
        self.server_name = server_name

    @staticmethod
    def _store(state: AgentState) -> EvidenceStore:
        store = EvidenceStore()
        for raw in state["evidence"]:
            values = dict(raw)
            values.pop("quality", None)
            values.pop("id", None)
            values["source_type"] = SourceType(values["source_type"])
            store.create(**values)
        return store

    async def _call(self, tool: str, arguments: dict[str, Any]) -> Any:
        return await self.manager.call_tool(self.server_name, tool, arguments)

    async def research(self, state: AgentState) -> dict:
        if not state["knowledge_enabled"]:
            return {"documentation_searched": False}
        store = self._store(state)
        notes = list(state["supervisor_notes"])
        seen: set[tuple[str | None, int | None, str]] = set()

        try:
            semantic = await self._call("semantic_search", {"query": state["request"], "limit": 5})
        except Exception as exc:
            semantic = {"matches": []}
            notes.append(f"Qdrant semantic search was unavailable; continued with non-RAG retrieval: {exc}")
        paths = [item["path"] for item in semantic.get("matches", []) if item.get("source") == "documentation"]
        repository_candidates = [item for item in semantic.get("matches", []) if item.get("source") == "repository"]
        for candidate in repository_candidates[:3]:
            try:
                current = await self.manager.call_tool("repository", "read_file", {"path": candidate["path"]})
                lines = current["content"].splitlines()
                start = max(1, int(candidate.get("start_line", 1)))
                end = min(len(lines), int(candidate.get("end_line", start)))
                if end < start:
                    raise ValueError("indexed line range no longer exists")
                current_text = "\n".join(lines[start - 1:end]).strip()
                store.create(
                    source_type=SourceType.REPOSITORY,
                    file=candidate["path"],
                    line_start=start,
                    line_end=end,
                    symbol=candidate.get("symbol"),
                    observation=f"RAG candidate verified through Repository MCP: {current_text[:500]}",
                    reliability=1.0,
                    relevance=max(0.0, min(1.0, float(candidate.get("score", 0.5)))),
                )
            except Exception as exc:
                notes.append(f"Discarded stale RAG repository candidate {candidate.get('path')}: {exc}")
        auth_issue = any(term in state["request"].casefold() for term in ("login", "auth", "401", "token", "jwt", "refresh"))
        queries = list(dict.fromkeys(state["evidence_requests"] + (["refresh", "401", "JWT_SECRET"] if auth_issue else [])))
        for query in queries:
            result = await self._call("search_docs", {"query": query})
            for match in result.get("matches", []):
                observation = f"Documentation states near {query!r}: {match['text']}"
                key = (match["path"], match["line"], observation)
                if key in seen:
                    continue
                store.create(
                    source_type=SourceType.DOCUMENTATION,
                    file=match["path"],
                    line_start=match["line"],
                    line_end=match["line"],
                    observation=observation,
                    reliability=0.9,
                    relevance=0.95,
                )
                seen.add(key)
                paths.append(match["path"])

        if auth_issue:
            library = await self._call("search_library_docs", {"library": "PyJWT", "query": "decode"})
            for match in library.get("matches", []):
                observation = f"PyJWT documentation reference: {match['text']}"
                key = (match["path"], match["line"], observation)
                if key not in seen:
                    store.create(
                        source_type=SourceType.DOCUMENTATION,
                        file=match["path"],
                        line_start=match["line"],
                        line_end=match["line"],
                        symbol="jwt.decode",
                        observation=observation,
                        reliability=0.95,
                        relevance=0.95,
                    )
                    seen.add(key)
                    paths.append(match["path"])

        # Read the highest-ranked unique documents to ground snippets in full context.
        for path in list(dict.fromkeys(paths))[:3]:
            await self._call("get_document", {"path": path})
        notes.append(f"Documentation Agent consulted {len(set(paths))} relevant technical/internal document(s).")
        return {
            "evidence": [item.to_dict() for item in store.all()],
            "documentation_searched": True,
            "supervisor_notes": notes,
        }
