from __future__ import annotations

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from mcp_clients.manager import MCPManager
from mcp_clients.registry import DEFAULT_KNOWLEDGE_ROOT, create_agent_registry, create_default_registry
from services.agents import RepositoryAgentGraph


class RepositoryAgentGraphTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _registry():
        root = Path(__file__).resolve().parents[1] / "sample_repos" / "vulnerable-fastapi-app"
        return create_default_registry(root)

    async def test_bug_request_delegates_for_more_evidence(self) -> None:
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}):
            async with MCPManager(self._registry()) as manager:
                result = await RepositoryAgentGraph(manager).run("Login returns 401 after refresh.")
        self.assertEqual(result["request_kind"], "bug_investigation")
        self.assertEqual(result["iteration"], 2)
        self.assertTrue(any("More evidence required" in note for note in result["supervisor_notes"]))
        self.assertGreaterEqual(len(result["hypotheses"]), 2)
        self.assertIn("Ranked hypotheses", result["final_report"])

    async def test_code_question_skips_bug_investigator(self) -> None:
        with patch.dict(os.environ, {"LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}):
            async with MCPManager(self._registry()) as manager:
                result = await RepositoryAgentGraph(manager).run("Where is authentication implemented?")
        self.assertEqual(result["request_kind"], "code_question")
        self.assertEqual(result["iteration"], 1)
        self.assertEqual(result["hypotheses"], [])
        self.assertIn("relevant implementation locations", result["final_report"])

    async def test_bug_investigation_combines_code_and_documentation_evidence(self) -> None:
        root = Path(__file__).resolve().parents[1] / "sample_repos" / "vulnerable-fastapi-app"
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
            "QDRANT_PATH": str(Path(temp) / "qdrant"),
        }):
            registry = create_agent_registry(root, knowledge_root=DEFAULT_KNOWLEDGE_ROOT)
            async with MCPManager(registry) as manager:
                result = await RepositoryAgentGraph(manager).run("Login returns 401 after refresh.")
        source_types = {item["source_type"] for item in result["evidence"]}
        self.assertIn("repository", source_types)
        self.assertIn("documentation", source_types)
        self.assertTrue(result["documentation_searched"])
        self.assertTrue(any("Documentation Agent consulted" in note for note in result["supervisor_notes"]))
        self.assertTrue(result["investigation_trace"])
        self.assertIn(result["termination_reason"], {"evidence sufficient", "iteration limit reached"})
        self.assertIn("Root cause decision", result["final_report"])


if __name__ == "__main__":
    unittest.main()
