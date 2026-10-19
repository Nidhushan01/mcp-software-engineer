"""One managed connection to one MCP server."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any

from mcp import Client, StdioServerParameters

from .registry import ServerConfig


class MCPSession:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        parameters = StdioServerParameters(
            command=config.command,
            args=list(config.args),
            cwd=str(config.cwd),
            env=config.env,
        )
        self._client = Client(parameters)
        self._connected = False

    async def __aenter__(self) -> "MCPSession":
        await self._client.__aenter__()
        self._connected = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        self._connected = False
        return await self._client.__aexit__(exc_type, exc_value, traceback)

    def _require_connection(self) -> None:
        if not self._connected:
            raise RuntimeError(f"MCP session is not connected: {self.config.name}")

    async def list_tools(self) -> list[dict[str, Any]]:
        self._require_connection()
        result = await self._client.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.input_schema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        self._require_connection()
        result = await self._client.call_tool(name, arguments or {})
        if result.is_error:
            message = " ".join(block.text for block in result.content if hasattr(block, "text"))
            raise RuntimeError(message or f"MCP tool failed: {self.config.name}.{name}")
        if result.structured_content is not None:
            return result.structured_content
        text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    async def read_resource(self, uri: str) -> str:
        self._require_connection()
        result = await self._client.read_resource(uri)
        return "\n".join(item.text for item in result.contents if hasattr(item, "text"))
