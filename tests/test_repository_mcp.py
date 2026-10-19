from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_clients.manager import MCPManager
from mcp_clients.registry import create_default_registry
from mcp_servers.repository.dependency_tools import get_dependencies
from mcp_servers.repository.git_tools import git_log, git_status
from mcp_servers.repository.security import RepositoryAccessError, resolve_repository_path
from mcp_servers.repository.tools import find_symbol, read_file, search_imports


class RepositoryToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src" / "auth.py").write_text(
            "from jwt import encode\n\ndef authenticate(user):\n    return encode({'sub': user}, 'secret')\n",
            encoding="utf-8",
        )
        (self.root / "requirements.txt").write_text("PyJWT==2.10.1\n", encoding="utf-8")
        self.environment = patch.dict(os.environ, {"REPOSITORY_ROOT": str(self.root)})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_navigation_search_and_dependencies(self) -> None:
        self.assertIn("authenticate", read_file("src/auth.py")["content"])
        self.assertEqual(find_symbol("authenticate")["count"], 1)
        self.assertEqual(search_imports("jwt")["count"], 1)
        self.assertEqual(get_dependencies()["dependencies"][0]["version"], "==2.10.1")

    def test_security_boundary(self) -> None:
        with self.assertRaises(RepositoryAccessError):
            resolve_repository_path("../outside.txt")
        with self.assertRaises(RepositoryAccessError):
            resolve_repository_path(str(self.root / "src" / "auth.py"))

    def test_git_tools(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.root, check=True)
        self.assertTrue(git_status()["clean"])
        self.assertEqual(git_log(1)["commits"][0]["subject"], "initial")


class MCPIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_protocol_tools_and_nested_resource(self) -> None:
        sample = Path(__file__).resolve().parents[1] / "sample_repos" / "vulnerable-fastapi-app"
        async with MCPManager(create_default_registry(sample)) as manager:
            tools = await manager.list_tools()
            self.assertEqual(len(tools), 16)
            result = await manager.call_namespaced_tool("repository__find_symbol", {"name": "login"})
            self.assertEqual(result["matches"][0]["path"], "app/api/auth.py")
            resource = await manager.read_resource("repository", "repo://file/app/api/auth.py")
            self.assertIn("def login", resource)


if __name__ == "__main__":
    unittest.main()
