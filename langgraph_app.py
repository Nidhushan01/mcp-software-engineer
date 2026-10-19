"""Run the supervised Repository MCP agent graph."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp_clients.manager import MCPManager
from mcp_clients.registry import DEFAULT_KNOWLEDGE_ROOT, DEFAULT_REPOSITORY_ROOT, create_agent_registry
from services.agents import RepositoryAgentGraph


async def run(
    request: str,
    repository: Path,
    max_iterations: int,
    output: Path | None,
    github: str | None,
    knowledge_root: Path | None,
    refresh_index: bool = False,
) -> None:
    if github and (github.count("/") != 1 or not all(github.split("/"))):
        raise ValueError("--github must use OWNER/REPOSITORY format")
    owner, repo = github.split("/", 1) if github else (None, None)
    registry = create_agent_registry(repository, include_github=bool(github), knowledge_root=knowledge_root)
    async with MCPManager(registry) as manager:
        if knowledge_root is not None and refresh_index:
            result = await manager.call_tool("knowledge", "refresh_index", {})
            print(f"Qdrant index refreshed: {result['chunks']} chunks")
        state = await RepositoryAgentGraph(manager).run(
            request,
            max_iterations,
            github_owner=owner,
            github_repo=repo,
        )
    report = state["final_report"]
    if output:
        output.write_text(report, encoding="utf-8")
        print(f"Supervisor report written to {output}")
    else:
        print(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the LangGraph repository supervisor")
    parser.add_argument("request", help="Repository question or bug report")
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPOSITORY_ROOT)
    parser.add_argument("--max-iterations", type=int, default=3)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github", metavar="OWNER/REPO", help="Enable read-only GitHub history research")
    parser.add_argument("--knowledge-root", type=Path, default=DEFAULT_KNOWLEDGE_ROOT)
    parser.add_argument("--no-knowledge", action="store_true", help="Disable the Documentation Agent")
    parser.add_argument("--refresh-index", action="store_true", help="Rebuild the Qdrant RAG index before investigating")
    args = parser.parse_args()
    knowledge_root = None if args.no_knowledge else args.knowledge_root.resolve()
    asyncio.run(run(args.request, args.repository.resolve(), args.max_iterations, args.output, args.github, knowledge_root, args.refresh_index))


if __name__ == "__main__":
    main()
