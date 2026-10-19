"""Lifecycle and routing manager for multiple MCP server sessions."""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from .registry import MCPRegistry
from .session import MCPSession


class MCPManager:
    """Connect registered servers and route namespaced tool calls."""

    separator = "__"

    def __init__(self, registry: MCPRegistry) -> None:
        self.registry = registry
        self._stack: AsyncExitStack | None = None
        self._sessions: dict[str, MCPSession] = {}

    async def __aenter__(self) -> "MCPManager":
        self._stack = AsyncExitStack()
        await self._stack.__aenter__()
        try:
            for name in self.registry.names():
                session = MCPSession(self.registry.get(name))
                self._sessions[name] = await self._stack.enter_async_context(session)
        except BaseException:
            await self._stack.aclose()
            self._stack = None
            self._sessions.clear()
            raise
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> bool | None:
        if self._stack is None:
            return None
        try:
            return await self._stack.__aexit__(exc_type, exc_value, traceback)
        finally:
            self._stack = None
            self._sessions.clear()

    def _session(self, server_name: str) -> MCPSession:
        try:
            return self._sessions[server_name]
        except KeyError as exc:
            raise RuntimeError(f"MCP server is not connected: {server_name}") from exc

    def has_server(self, server_name: str) -> bool:
        return server_name in self._sessions

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self._session(server_name).call_tool(tool_name, arguments)

    async def call_namespaced_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if self.separator not in name:
            raise ValueError(f"Tool name must be namespaced as server{self.separator}tool")
        server_name, tool_name = name.split(self.separator, 1)
        return await self.call_tool(server_name, tool_name, arguments)

    async def read_resource(self, server_name: str, uri: str) -> str:
        return await self._session(server_name).read_resource(uri)

    async def list_tools(self) -> list[dict[str, Any]]:
        catalog: list[dict[str, Any]] = []
        for server_name, session in self._sessions.items():
            for tool in await session.list_tools():
                catalog.append({**tool, "server": server_name, "name": f"{server_name}{self.separator}{tool['name']}"})
        return catalog

    async def openai_tools(self) -> list[dict[str, Any]]:
        """Convert connected MCP tools to OpenAI Responses function definitions."""
        return [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
                "strict": False,
            }
            for tool in await self.list_tools()
        ]
