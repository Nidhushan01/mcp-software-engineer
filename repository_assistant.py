"""Minimal LLM-to-MCP tool loop. No LangGraph or agent framework."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from mcp_clients.manager import MCPManager
from mcp_clients.registry import DEFAULT_REPOSITORY_ROOT, create_default_registry


INSTRUCTIONS = """You are a repository analysis assistant.
Use the repository tools to investigate before answering. Start broad, then narrow down:
inspect the structure, search for relevant concepts or symbols, and read the most relevant files.
Never invent code that was not returned by a tool. Cite repository-relative file paths in the answer.
All available tools are read-only.
"""


class RepositoryAssistant:
    def __init__(self, manager: MCPManager, model: str) -> None:
        self.manager = manager
        self.model = model
        self.client = AsyncOpenAI()

    async def ask(self, question: str, max_tool_rounds: int = 12) -> str:
        tools = await self.manager.openai_tools()
        inputs: list[Any] = [{"role": "user", "content": question}]

        for _ in range(max_tool_rounds):
            response = await self.client.responses.create(
                model=self.model,
                instructions=INSTRUCTIONS,
                tools=tools,
                input=inputs,
            )
            inputs.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return response.output_text

            for call in calls:
                try:
                    arguments = json.loads(call.arguments)
                    result = await self.manager.call_namespaced_tool(call.name, arguments)
                    output = json.dumps(result, ensure_ascii=False)
                except Exception as exc:  # Return tool errors so the model can recover.
                    output = json.dumps({"error": str(exc)})
                inputs.append({"type": "function_call_output", "call_id": call.call_id, "output": output})

        raise RuntimeError(f"The assistant exceeded {max_tool_rounds} tool rounds")


async def async_main(question: str, repository_root: Path, model: str) -> None:
    registry = create_default_registry(repository_root)
    async with MCPManager(registry) as manager:
        assistant = RepositoryAssistant(manager, model)
        print(await assistant.ask(question))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask an LLM questions about a local repository through MCP")
    parser.add_argument("question", help="Question to answer about the repository")
    parser.add_argument("--repository", type=Path, default=DEFAULT_REPOSITORY_ROOT)
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-5.4"))
    args = parser.parse_args()
    asyncio.run(async_main(args.question, args.repository, args.model))


if __name__ == "__main__":
    main()
