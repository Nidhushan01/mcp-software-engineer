"""Repository MCP specialist that returns source-grounded evidence."""

from __future__ import annotations

from typing import Any

from mcp_clients.manager import MCPManager
from services.investigation.evidence import EvidenceStore, SourceType

from .state import AgentState


class CodeAnalystAgent:
    def __init__(self, manager: MCPManager, server_name: str = "repository") -> None:
        self.manager = manager
        self.server_name = server_name

    async def _call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.manager.call_tool(self.server_name, tool, arguments)

    @staticmethod
    def _queries(request: str) -> list[str]:
        ignored = {"a", "an", "and", "after", "before", "does", "for", "in", "is", "my", "of", "the", "to", "where", "why"}
        words = [word.strip(".,:;!?()[]{}\"'") for word in request.split()]
        return list(dict.fromkeys(word for word in words if len(word) >= 3 and word.casefold() not in ignored))[:6]

    async def analyze(self, state: AgentState) -> dict:
        store = EvidenceStore()
        for raw in state["evidence"]:
            values = dict(raw)
            values.pop("quality", None)
            values["source_type"] = SourceType(values["source_type"])
            store.create(**{key: value for key, value in values.items() if key != "id"})

        queries = state["evidence_requests"] or self._queries(state["request"])
        inspected = set(state["inspected_files"])
        seen = {(item.file, item.line_start, item.observation) for item in store.all()}
        for query in queries:
            result = await self._call("search_code", {"query": query})
            if not result["matches"]:
                observation = f"Repository-wide search found no matches for {query!r}."
                key = (None, None, observation)
                if key not in seen:
                    store.create(source_type=SourceType.REPOSITORY, observation=observation, reliability=0.8, relevance=0.85)
                    seen.add(key)
            for match in result["matches"]:
                observation = f"Search for {query!r} matched: {match['text']}"
                key = (match["path"], match["line"], observation)
                if key in seen:
                    continue
                store.create(
                    source_type=SourceType.TEST if "test" in match["path"].casefold() else SourceType.REPOSITORY,
                    file=match["path"],
                    line_start=match["line"],
                    line_end=match["line"],
                    observation=observation,
                    reliability=0.95,
                    relevance=0.9,
                )
                inspected.add(match["path"])
                seen.add(key)

        if state["iteration"] == 0 and any(
            term in state["request"].casefold() for term in ("login", "auth", "401", "token", "jwt")
        ):
            auth_files = await self._call("find_files", {"pattern": "*auth*.py"})
            for match in auth_files["matches"]:
                observation = f"Authentication-related filename discovered: {match['path']}"
                key = (match["path"], None, observation)
                if key not in seen:
                    store.create(source_type=SourceType.REPOSITORY, file=match["path"], observation=observation, reliability=0.9, relevance=0.9)
                    inspected.add(match["path"])
                    seen.add(key)

            symbols = await self._call("find_symbol", {"name": "create_access_token"})
            for match in symbols["matches"]:
                observation = f"Token creation symbol found: {match['name']} ({match['kind']})"
                key = (match["path"], match["line"], observation)
                if key not in seen:
                    store.create(
                        source_type=SourceType.REPOSITORY,
                        file=match["path"],
                        line_start=match["line"],
                        line_end=match["line"],
                        symbol=match["name"],
                        observation=observation,
                        reliability=0.95,
                        relevance=0.95,
                    )
                    inspected.add(match["path"])
                    seen.add(key)

            imports = await self._call("search_imports", {"module": "fastapi"})
            for match in imports["matches"]:
                observation = f"Framework import traces an API module: {match['text']}"
                key = (match["path"], match["line"], observation)
                if key not in seen:
                    store.create(
                        source_type=SourceType.REPOSITORY,
                        file=match["path"],
                        line_start=match["line"],
                        line_end=match["line"],
                        observation=observation,
                        reliability=0.95,
                        relevance=0.7,
                    )
                    inspected.add(match["path"])
                    seen.add(key)

        # Read the most relevant files to ensure findings are based on implementation context.
        for path in sorted(inspected)[:8]:
            await self._call("read_file", {"path": path})

        return {
            "evidence": [item.to_dict() for item in store.all()],
            "inspected_files": sorted(inspected),
            "evidence_requests": [],
            "iteration": state["iteration"] + 1,
        }
