"""Configuration registry for local MCP servers."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY_ROOT = PROJECT_ROOT / "sample_repos" / "vulnerable-fastapi-app"
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge_base"


@dataclass(frozen=True)
class ServerConfig:
    name: str
    command: str
    args: tuple[str, ...]
    cwd: Path
    env: dict[str, str] = field(default_factory=dict, repr=False)


class MCPRegistry:
    """Store server launch configurations without opening connections."""

    def __init__(self) -> None:
        self._servers: dict[str, ServerConfig] = {}

    def register(self, config: ServerConfig) -> None:
        if not config.name or "__" in config.name:
            raise ValueError("Server name must be non-empty and cannot contain '__'")
        if config.name in self._servers:
            raise ValueError(f"MCP server is already registered: {config.name}")
        self._servers[config.name] = config

    def get(self, name: str) -> ServerConfig:
        try:
            return self._servers[name]
        except KeyError as exc:
            raise KeyError(f"Unknown MCP server: {name}") from exc

    def names(self) -> list[str]:
        return sorted(self._servers)


def create_default_registry(repository_root: str | Path = DEFAULT_REPOSITORY_ROOT) -> MCPRegistry:
    registry = MCPRegistry()
    registry.register(
        ServerConfig(
            name="repository",
            command=sys.executable,
            args=("-m", "mcp_servers.repository.server"),
            cwd=PROJECT_ROOT,
            env={"REPOSITORY_ROOT": str(Path(repository_root).resolve())},
        )
    )
    return registry


def create_github_config(token: str | None = None) -> ServerConfig:
    """Configure GitHub's official MCP Docker image in strict read-only mode."""
    github_token = token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not github_token:
        raise ValueError("Set GITHUB_PERSONAL_ACCESS_TOKEN before enabling GitHub MCP")
    return ServerConfig(
        name="github",
        command="docker",
        args=(
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "-e", "GITHUB_TOOLSETS",
            "-e", "GITHUB_READ_ONLY",
            "-e", "GITHUB_LOCKDOWN_MODE",
            "ghcr.io/github/github-mcp-server",
        ),
        cwd=PROJECT_ROOT,
        env={
            "GITHUB_PERSONAL_ACCESS_TOKEN": github_token,
            "GITHUB_TOOLSETS": "repos,issues,pull_requests,discussions",
            "GITHUB_READ_ONLY": "1",
            "GITHUB_LOCKDOWN_MODE": "1",
        },
    )


def create_agent_registry(
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
    *,
    include_github: bool = False,
    github_token: str | None = None,
    knowledge_root: str | Path | None = None,
) -> MCPRegistry:
    registry = create_default_registry(repository_root)
    if include_github:
        registry.register(create_github_config(github_token))
    if knowledge_root is not None:
        registry.register(create_knowledge_config(knowledge_root, repository_root))
    return registry


def create_knowledge_config(
    knowledge_root: str | Path = DEFAULT_KNOWLEDGE_ROOT,
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
) -> ServerConfig:
    root = Path(knowledge_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Knowledge root is not a directory: {root}")
    return ServerConfig(
        name="knowledge",
        command=sys.executable,
        args=("-m", "mcp_servers.knowledge.server"),
        cwd=PROJECT_ROOT,
        env={
            "KNOWLEDGE_ROOT": str(root),
            "REPOSITORY_ROOT": str(Path(repository_root).resolve()),
            "QDRANT_PATH": os.getenv("QDRANT_PATH", str(PROJECT_ROOT / ".qdrant_data")),
            "QDRANT_URL": os.getenv("QDRANT_URL", ""),
            "QDRANT_API_KEY": os.getenv("QDRANT_API_KEY", ""),
        },
    )


def create_patch_config(repository_root: str | Path = DEFAULT_REPOSITORY_ROOT) -> ServerConfig:
    """Create the separately permissioned, write-capable Patch MCP config."""
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root is not a directory: {root}")
    return ServerConfig(
        name="patch",
        command=sys.executable,
        args=("-m", "mcp_servers.patch.server"),
        cwd=PROJECT_ROOT,
        env={"REPOSITORY_ROOT": str(root)},
    )
