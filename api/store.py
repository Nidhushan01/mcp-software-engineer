from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp_clients.manager import MCPManager
from mcp_clients.registry import MCPRegistry, create_patch_config
from services.agents import PatchApprovalWorkflow


def now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RepositoryRecord:
    id: str
    name: str
    path: Path
    connected_at: datetime = field(default_factory=now)


@dataclass
class InvestigationRecord:
    id: str
    repository_id: str
    issue: str
    status: str = "queued"
    created_at: datetime = field(default_factory=now)
    updated_at: datetime = field(default_factory=now)
    state: dict[str, Any] | None = None
    error: str | None = None
    patch: dict[str, Any] | None = None


class PatchRuntime:
    """Own an MCP stdio session in one task while HTTP requests send commands."""

    def __init__(self, repository: Path, thread_id: str) -> None:
        self.repository = repository
        self.thread_id = thread_id
        self.queue: asyncio.Queue[tuple[str, tuple[Any, ...], asyncio.Future[Any]]] = asyncio.Queue()
        self.task: asyncio.Task[Any] | None = None
        self.ready: asyncio.Future[None] | None = None

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self.ready = loop.create_future()
        self.task = asyncio.create_task(self._run())
        await self.ready

    async def _run(self) -> None:
        registry = MCPRegistry()
        registry.register(create_patch_config(self.repository))
        try:
            async with MCPManager(registry) as manager:
                workflow = PatchApprovalWorkflow(manager)
                assert self.ready is not None
                self.ready.set_result(None)
                while True:
                    operation, arguments, future = await self.queue.get()
                    if operation == "close":
                        future.set_result(None)
                        return
                    try:
                        if operation == "propose":
                            result = await workflow.propose(*arguments, self.thread_id)
                        else:
                            result = await workflow.resume(self.thread_id, *arguments)
                        future.set_result(result)
                    except BaseException as exc:
                        future.set_exception(exc)
        except BaseException as exc:
            if self.ready is not None and not self.ready.done():
                self.ready.set_exception(exc)
            raise

    async def call(self, operation: str, *arguments: Any) -> Any:
        future = asyncio.get_running_loop().create_future()
        await self.queue.put((operation, arguments, future))
        return await future

    async def close(self) -> None:
        if self.task is None or self.task.done():
            return
        await self.call("close")
        await self.task


class APIStore:
    def __init__(self) -> None:
        self.repositories: dict[str, RepositoryRecord] = {}
        self.investigations: dict[str, InvestigationRecord] = {}
        self.patch_runtimes: dict[str, PatchRuntime] = {}
        self.tasks: set[asyncio.Task[Any]] = set()
        self.repository_locks: dict[str, asyncio.Lock] = {}

    async def close(self) -> None:
        for task in self.tasks:
            if not task.done():
                task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        for runtime in list(self.patch_runtimes.values()):
            await runtime.close()
        self.patch_runtimes.clear()
