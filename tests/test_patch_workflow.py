from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_clients.manager import MCPManager
from mcp_clients.registry import MCPRegistry, create_patch_config
from mcp_servers.patch.tools import apply_patch, generate_diff, validate_patch
from services.agents import PatchApprovalWorkflow

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"


class PatchToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app.py").write_text("value = 1\n", encoding="utf-8")
        self.environment = patch.dict(os.environ, {"REPOSITORY_ROOT": str(self.root)})
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temp.cleanup()

    def test_proposal_validation_does_not_write_and_apply_requires_exact_approval(self) -> None:
        proposal = generate_diff("app.py", "value = 2\n")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "value = 1\n")
        self.assertTrue(validate_patch(proposal["proposal_id"])["valid"])
        with self.assertRaises(PermissionError):
            apply_patch(proposal["proposal_id"], "yes")
        result = apply_patch(proposal["proposal_id"], f"APPROVE {proposal['proposal_id']}")
        self.assertEqual(result["status"], "applied")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "value = 2\n")

    def test_stale_and_syntax_invalid_proposals_are_rejected(self) -> None:
        invalid = generate_diff("app.py", "def broken(:\n")
        self.assertFalse(validate_patch(invalid["proposal_id"])["valid"])
        stale = generate_diff("app.py", "value = 3\n")
        (self.root / "app.py").write_text("value = 99\n", encoding="utf-8")
        self.assertFalse(validate_patch(stale["proposal_id"])["checks"]["source_unchanged"])


class PatchApprovalWorkflowTest(unittest.IsolatedAsyncioTestCase):
    async def test_reject_stops_without_writing_and_approve_applies(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "app.py"
            target.write_text("value = 1\n", encoding="utf-8")
            registry = MCPRegistry()
            registry.register(create_patch_config(root))
            async with MCPManager(registry) as manager:
                workflow = PatchApprovalWorkflow(manager)
                pending = await workflow.propose("app.py", "value = 2\n", "reject-case")
                self.assertIn("__interrupt__", pending)
                self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")
                rejected = await workflow.resume("reject-case", "reject")
                self.assertEqual(rejected["approval_status"], "reject")
                self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")

                await workflow.propose("app.py", "value = 7\n", "changes-case")
                changed = await workflow.resume("changes-case", "request_changes", "Use a named constant")
                self.assertEqual(changed["approval_status"], "request_changes")
                self.assertEqual(changed["feedback"], "Use a named constant")
                self.assertEqual(target.read_text(encoding="utf-8"), "value = 1\n")

                await workflow.propose("app.py", "value = 2\n", "approve-case")
                approved = await workflow.resume("approve-case", "approve")
                self.assertEqual(approved["approval_status"], "applied")
                self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")


if __name__ == "__main__":
    unittest.main()
