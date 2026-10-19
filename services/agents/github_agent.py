"""GitHub history specialist backed by GitHub's official MCP server."""

from __future__ import annotations

import json
import re
from typing import Any

from mcp_clients.manager import MCPManager
from services.investigation.evidence import EvidenceStore, SourceType

from .state import AgentState


class GitHubHistoryAgent:
    """Collect historical context only; never performs general code analysis."""

    def __init__(self, manager: MCPManager, server_name: str = "github") -> None:
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

    @staticmethod
    def _records(value: Any) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if isinstance(value, dict):
            if any(key in value for key in ("number", "sha", "title", "html_url")):
                records.append(value)
            for child in value.values():
                records.extend(GitHubHistoryAgent._records(child))
        elif isinstance(value, list):
            for child in value:
                records.extend(GitHubHistoryAgent._records(child))
        return records

    @staticmethod
    def _summary(kind: str, value: dict[str, Any]) -> str:
        identity = value.get("number") or str(value.get("sha", ""))[:12] or "result"
        title = value.get("title") or value.get("commit", {}).get("message") or value.get("name") or ""
        url = value.get("html_url") or value.get("url") or ""
        text = f"GitHub {kind} {identity}: {title}".strip()
        return f"{text} ({url})" if url else text

    @staticmethod
    def _search_terms(request: str) -> str:
        words = re.findall(r"[A-Za-z0-9_\-]+", request)
        ignored = {"a", "after", "and", "before", "for", "is", "my", "the", "to", "when"}
        return " ".join(word for word in words if len(word) > 2 and word.casefold() not in ignored)[:180]

    async def research(self, state: AgentState) -> dict:
        if not state["github_enabled"]:
            return {"github_searched": False}
        owner, repo = state["github_owner"], state["github_repo"]
        store = self._store(state)
        notes = list(state["supervisor_notes"])
        follow_up = " ".join(state.get("evidence_requests", []))
        query = self._search_terms(f"{state['request']} {follow_up}")
        seen = {(item.source_type.value, item.observation) for item in store.all()}
        calls = [
            ("search_issues", {"query": query, "owner": owner, "repo": repo, "perPage": 5}, "issue"),
            ("search_pull_requests", {"query": query, "owner": owner, "repo": repo, "perPage": 5}, "pull request"),
            ("list_commits", {"owner": owner, "repo": repo, "perPage": 10}, "commit"),
            ("search_code", {"query": f"{query} repo:{owner}/{repo}", "perPage": 5}, "historical code result"),
            ("list_discussions", {"owner": owner, "repo": repo, "perPage": 10}, "discussion"),
        ]
        results: dict[str, list[dict[str, Any]]] = {}
        for tool, arguments, kind in calls:
            try:
                raw = await self.manager.call_tool(self.server_name, tool, arguments)
                records = self._records(raw)[:10]
                results[tool] = records
                for record in records[:5]:
                    observation = self._summary(kind, record)
                    if (SourceType.GITHUB.value, observation) in seen:
                        continue
                    store.create(
                        source_type=SourceType.GITHUB,
                        observation=observation,
                        reliability=0.9,
                        relevance=0.8 if tool != "list_commits" else 0.6,
                    )
                    seen.add((SourceType.GITHUB.value, observation))
            except Exception as exc:
                notes.append(f"GitHub MCP {tool} was unavailable: {exc}")

        # Inspect the strongest matching issue, PR, and recent commit for context.
        detail_calls: list[tuple[str, dict[str, Any], str]] = []
        issues = results.get("search_issues", [])
        if issues and isinstance(issues[0].get("number"), int):
            detail_calls.append(("issue_read", {"method": "get", "owner": owner, "repo": repo, "issue_number": issues[0]["number"]}, "issue detail"))
        pulls = results.get("search_pull_requests", [])
        if pulls and isinstance(pulls[0].get("number"), int):
            detail_calls.append(("pull_request_read", {"method": "get", "owner": owner, "repo": repo, "pullNumber": pulls[0]["number"]}, "pull request detail"))
        commits = results.get("list_commits", [])
        if commits and commits[0].get("sha"):
            detail_calls.append(("get_commit", {"owner": owner, "repo": repo, "sha": commits[0]["sha"], "detail": "stats"}, "commit detail"))
        discussions = results.get("list_discussions", [])
        if discussions and isinstance(discussions[0].get("number"), int):
            detail_calls.append(("get_discussion", {"owner": owner, "repo": repo, "discussionNumber": discussions[0]["number"]}, "discussion detail"))
        for tool, arguments, kind in detail_calls:
            try:
                raw = await self.manager.call_tool(self.server_name, tool, arguments)
                compact = json.dumps(raw, ensure_ascii=False, default=str)
                store.create(
                    source_type=SourceType.GITHUB,
                    observation=f"GitHub {kind}: {compact[:900]}",
                    reliability=0.95,
                    relevance=0.85,
                )
            except Exception as exc:
                notes.append(f"GitHub MCP {tool} was unavailable: {exc}")

        notes.append(f"GitHub History Agent searched {owner}/{repo} for issues, PRs, commits, discussions, and prior code context.")
        return {
            "evidence": [item.to_dict() for item in store.all()],
            "github_searched": True,
            "supervisor_notes": notes,
        }
