from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_clients.manager import MCPManager
from mcp_clients.registry import MCPRegistry, create_knowledge_config
from mcp_servers.knowledge.security import KnowledgeAccessError, resolve_document_path
from mcp_servers.knowledge.rag import close_rag_clients
from mcp_servers.knowledge.tools import find_related_documents, get_api_reference, refresh_index, search_docs, search_library_docs, semantic_search


class KnowledgeToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "libraries").mkdir()
        (self.root / "auth.md").write_text("# Authentication\nRefresh tokens require signature validation and return 401 when expired.\n", encoding="utf-8")
        (self.root / "libraries" / "pyjwt.md").write_text("# PyJWT\nUse `jwt.decode()` to validate a token signature.\n", encoding="utf-8")
        self.repository = self.root / "repository"
        (self.repository / "app" / "services").mkdir(parents=True)
        (self.repository / "app" / "services" / "auth_service.py").write_text(
            "def create_access_token(user_id):\n    return jwt.encode({'sub': user_id}, JWT_SECRET)\n",
            encoding="utf-8",
        )
        self.environment = patch.dict(os.environ, {
            "KNOWLEDGE_ROOT": str(self.root),
            "REPOSITORY_ROOT": str(self.repository),
            "QDRANT_PATH": ":memory:",
        })
        self.environment.start()

    def tearDown(self) -> None:
        close_rag_clients()
        self.environment.stop()
        self.temp.cleanup()

    def test_all_retrieval_modes(self) -> None:
        self.assertEqual(search_docs("401")["count"], 1)
        self.assertEqual(search_library_docs("PyJWT", "decode")["count"], 1)
        self.assertEqual(get_api_reference("jwt.decode")["count"], 1)
        indexed = refresh_index()
        self.assertEqual(indexed["sources"]["repository"], 1)
        self.assertEqual(semantic_search("refresh authentication")["matches"][0]["path"], "auth.md")
        repository_match = semantic_search("create access token", 10)["matches"]
        repository_match = next(match for match in repository_match if match["source"] == "repository")
        self.assertEqual(repository_match["symbol"], "create_access_token")
        self.assertEqual(repository_match["language"], "python")
        self.assertEqual(repository_match["start_line"], 1)
        self.assertEqual(repository_match["end_line"], 2)
        self.assertEqual(find_related_documents("auth.md")["count"], 1)

    def test_security_boundary(self) -> None:
        with self.assertRaises(KnowledgeAccessError):
            resolve_document_path("../outside.md")


class KnowledgeMCPIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_tools_and_nested_document_resource(self) -> None:
        root = Path(__file__).resolve().parents[1] / "knowledge_base"
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {"QDRANT_PATH": str(Path(temp) / "qdrant")}):
            registry = MCPRegistry()
            registry.register(create_knowledge_config(root))
            async with MCPManager(registry) as manager:
                tools = await manager.list_tools()
                self.assertEqual(len(tools), 7)
                rebuilt = await manager.call_tool("knowledge", "refresh_index", {})
                self.assertGreater(rebuilt["chunks"], 0)
                result = await manager.call_tool("knowledge", "semantic_search", {"query": "refresh token 401"})
                self.assertEqual(result["backend"], "qdrant")
                self.assertTrue(result["matches"])
                document = await manager.read_resource("knowledge", "knowledge://document/internal/authentication.md")
                self.assertIn("Required refresh behavior", document)


if __name__ == "__main__":
    unittest.main()
