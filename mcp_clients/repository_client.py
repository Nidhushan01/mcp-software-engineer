"""Small async client for the repository MCP server."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import TracebackType
from typing import Any
from urllib.parse import quote

from mcp import Client, StdioServerParameters


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_ROOT = PROJECT_ROOT / "sample_repos" / "vulnerable-fastapi-app"


class RepositoryClient:
    """Convenience wrapper around a stdio MCP client connection."""

    def __init__(self, repository_root: str | Path = DEFAULT_REPOSITORY_ROOT) -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_servers.repository.server"],
            cwd=str(PROJECT_ROOT),
            env={"REPOSITORY_ROOT": str(Path(repository_root).resolve())},
        )
        self._client = Client(parameters)

    async def __aenter__(self) -> "RepositoryClient":
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        return await self._client.__aexit__(exc_type, exc_value, traceback)

    async def _call(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = await self._client.call_tool(name, arguments or {})
        if result.is_error:
            message = " ".join(
                block.text for block in result.content if hasattr(block, "text")
            )
            raise RuntimeError(message or f"Repository tool failed: {name}")
        if result.structured_content is not None:
            return result.structured_content
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    async def list_directory(self, path: str = ".") -> dict[str, Any]:
        return await self._call("list_directory", {"path": path})

    async def read_file(self, path: str) -> dict[str, Any]:
        return await self._call("read_file", {"path": path})

    async def search_code(self, query: str) -> dict[str, Any]:
        return await self._call("search_code", {"query": query})

    async def get_repository_structure(self) -> dict[str, Any]:
        return await self._call("get_repository_structure")

    async def read_structure_resource(self) -> str:
        result = await self._client.read_resource("repo://structure")
        return "\n".join(
            content.text for content in result.contents if hasattr(content, "text")
        )

    async def read_file_resource(self, path: str) -> str:
        encoded_path = quote(path.replace("\\", "/"), safe="/")
        result = await self._client.read_resource(f"repo://file/{encoded_path}")
        return "\n".join(
            content.text for content in result.contents if hasattr(content, "text")
        )
