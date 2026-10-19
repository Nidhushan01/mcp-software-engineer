from __future__ import annotations

import unittest
from pathlib import Path

from mcp_clients.manager import MCPManager
from mcp_clients.registry import create_default_registry
from services.investigation import Evidence, EvidenceStore, InvestigationEngine, InvestigationPlanner, SourceType
from services.investigation.confidence import ConfidenceScorer
from services.investigation.hypotheses import Hypothesis, HypothesisStatus


class InvestigationModelsTest(unittest.TestCase):
    def test_authentication_plan_has_expected_ten_steps(self) -> None:
        plan = InvestigationPlanner().create("Login returns 401 after refresh.")
        self.assertEqual(len(plan.steps), 10)
        self.assertEqual(plan.steps[0].objective, "Locate authentication endpoints")
        self.assertEqual(plan.steps[-1].objective, "Produce evidence-backed recommendations")

    def test_evidence_validates_line_provenance(self) -> None:
        with self.assertRaises(ValueError):
            Evidence("E1", SourceType.REPOSITORY, "Observed code", line_start=4, line_end=6)

    def test_confidence_and_status(self) -> None:
        store = EvidenceStore()
        item = store.create(source_type=SourceType.TEST, observation="A focused test reproduces the failure")
        hypothesis = Hypothesis("H1", "Refresh rejects a valid token", [item.id], explicitly_reproduced=True)
        ConfidenceScorer().evaluate(hypothesis, store)
        self.assertEqual(hypothesis.status, HypothesisStatus.CONFIRMED)
        self.assertGreaterEqual(hypothesis.confidence, 0.9)


class InvestigationIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_login_investigation_has_traceable_hypotheses(self) -> None:
        root = Path(__file__).resolve().parents[1] / "sample_repos" / "vulnerable-fastapi-app"
        async with MCPManager(create_default_registry(root)) as manager:
            report = await InvestigationEngine(manager).investigate("Login returns 401 after refresh.")
        self.assertEqual(len(report.plan.steps), 10)
        self.assertTrue(report.evidence.all())
        self.assertTrue(all(item.supporting_evidence for item in report.hypotheses))
        self.assertIn("no refresh-token implementation", report.to_markdown())


if __name__ == "__main__":
    unittest.main()
