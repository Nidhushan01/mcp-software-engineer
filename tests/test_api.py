from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app, store
from api.store import InvestigationRecord


class InvestigationAPITest(unittest.TestCase):
    def setUp(self) -> None:
        store.repositories.clear()
        store.investigations.clear()
        store.patch_runtimes.clear()
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app.py").write_text("value = 1\n", encoding="utf-8")
        self.environment = patch.dict(os.environ, {
            "REPOSITORY_ALLOWED_ROOT": str(self.root),
            "LANGSMITH_TRACING": "false",
            "LANGCHAIN_TRACING_V2": "false",
        })
        self.environment.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.environment.stop()
        self.temp.cleanup()

    def test_repository_boundary_and_investigation_creation(self) -> None:
        forbidden = self.client.post("/repositories/connect", json={"path": str(self.root.parent)})
        self.assertEqual(forbidden.status_code, 403)
        connected = self.client.post("/repositories/connect", json={"path": str(self.root), "name": "demo"})
        self.assertEqual(connected.status_code, 201)
        repository_id = connected.json()["id"]
        created = self.client.post("/investigations", json={
            "repository_id": repository_id,
            "issue": "Where is value defined?",
            "use_knowledge": False,
        })
        self.assertEqual(created.status_code, 202)
        self.assertIn(created.json()["status"], {"queued", "running", "completed"})

    def test_patch_requires_confirmed_hypothesis_and_human_approval(self) -> None:
        connected = self.client.post("/repositories/connect", json={"path": str(self.root)}).json()
        record = InvestigationRecord("case", connected["id"], "value bug", status="completed")
        record.state = {"hypotheses": [{"id": "H1", "status": "supported"}]}
        store.investigations[record.id] = record
        blocked = self.client.post("/investigations/case/patch", json={"path": "app.py", "new_content": "value = 2\n"})
        self.assertEqual(blocked.status_code, 409)

        record.state["hypotheses"][0]["status"] = "confirmed"
        proposed = self.client.post("/investigations/case/patch", json={"path": "app.py", "new_content": "value = 2\n"})
        self.assertEqual(proposed.status_code, 202)
        self.assertEqual(proposed.json()["status"], "waiting_for_approval")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "value = 1\n")

        approved = self.client.post("/investigations/case/approve")
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["status"], "applied")
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "value = 2\n")


if __name__ == "__main__":
    unittest.main()
