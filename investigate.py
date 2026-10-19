"""Command-line entry point for the repository investigation engine."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from mcp_clients.manager import MCPManager
from mcp_clients.registry import DEFAULT_REPOSITORY_ROOT, create_default_registry
from services.investigation import InvestigationEngine


async def run(issue: str, repository: Path, output: Path | None) -> None:
    async with MCPManager(create_default_registry(repository)) as manager:
        report = await InvestigationEngine(manager).investigate(issue)
    markdown = report.to_markdown()
    if output:
        output.write_text(markdown, encoding="utf-8")
        print(f"Investigation report written to {output}")
    else:
        print(markdown)


def main() -> None:
    parser = argparse.ArgumentParser(description="Investigate a repository bug through read-only MCP tools")
    parser.add_argument("issue", help="Bug report or symptom to investigate")
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPOSITORY_ROOT)
    parser.add_argument("--output", type=Path, help="Optional Markdown report path")
    args = parser.parse_args()
    asyncio.run(run(args.issue, args.repository.resolve(), args.output))


if __name__ == "__main__":
    main()
