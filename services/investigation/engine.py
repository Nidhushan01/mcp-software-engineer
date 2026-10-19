"""Orchestrate an evidence-driven investigation through MCP tools."""

from __future__ import annotations

from typing import Any

from mcp_clients.manager import MCPManager

from .confidence import ConfidenceScorer
from .evidence import EvidenceStore, SourceType
from .hypotheses import Hypothesis
from .planner import InvestigationPlan, InvestigationPlanner, StepStatus
from .report import InvestigationReport


class InvestigationEngine:
    """Run a repeatable first-pass investigation and preserve its reasoning inputs."""

    def __init__(self, manager: MCPManager, server_name: str = "repository") -> None:
        self.manager = manager
        self.server_name = server_name
        self.planner = InvestigationPlanner()
        self.scorer = ConfidenceScorer()

    async def _call(self, tool: str, arguments: dict[str, Any] | None = None) -> Any:
        return await self.manager.call_tool(self.server_name, tool, arguments)

    async def investigate(self, issue: str) -> InvestigationReport:
        plan = self.planner.create(issue)
        evidence = EvidenceStore()
        limitations: list[str] = []
        lowered = issue.casefold()
        auth_issue = any(term in lowered for term in ("login", "auth", "401", "token", "jwt"))
        queries = ["authentication", "refresh", "JWT", "jwt.decode", "401"] if auth_issue else self._issue_queries(issue)

        structure = await self._call("get_repository_structure")
        plan.steps[0].status = StepStatus.COMPLETE
        plan.steps[0].notes.append(f"Inspected repository tree rooted at {structure['name']}")

        search_results: dict[str, dict[str, Any]] = {}
        seen_locations: set[tuple[str, int, str]] = set()
        for query in queries:
            result = await self._call("search_code", {"query": query})
            search_results[query.casefold()] = result
            for match in result["matches"]:
                key = (match["path"], match["line"], match["text"])
                if key in seen_locations:
                    continue
                seen_locations.add(key)
                source_type = SourceType.TEST if "/test" in f"/{match['path'].casefold()}" else SourceType.REPOSITORY
                evidence.create(
                    source_type=source_type,
                    file=match["path"],
                    line_start=match["line"],
                    line_end=match["line"],
                    observation=f"Search for {query!r} matched: {match['text']}",
                    relevance=0.9 if query.casefold() in lowered else 0.8,
                    reliability=0.95,
                )

        for step in plan.steps[1:6] if auth_issue else plan.steps[1:3]:
            step.status = StepStatus.COMPLETE
            step.notes.append("Repository searches completed")

        test_step = next(step for step in plan.steps if "tests" in step.objective.casefold())
        tests = await self._call("find_files", {"pattern": "*test*.py"})
        test_step.status = StepStatus.COMPLETE
        test_step.notes.append(f"Found {tests['count']} test file(s)")

        git_step = next(step for step in plan.steps if "recent changes" in step.objective.casefold())
        root_entries = await self._call("list_directory", {"path": "."})
        is_git_repository = any(item["name"] == ".git" for item in root_entries["entries"])
        try:
            if not is_git_repository:
                raise RuntimeError("configured repository has no .git directory")
            log = await self._call("git_log", {"limit": 10})
            git_step.status = StepStatus.COMPLETE
            git_step.notes.append(f"Inspected {log['count']} recent commit(s)")
            for commit in log["commits"][:3]:
                evidence.create(
                    source_type=SourceType.GIT,
                    observation=f"Recent commit {commit['commit'][:12]}: {commit['subject']}",
                    relevance=0.5,
                    reliability=0.9,
                )
        except RuntimeError as exc:
            git_step.status = StepStatus.SKIPPED
            git_step.notes.append(str(exc))
            limitations.append(f"Git history was unavailable: {exc}")

        hypotheses = self._form_hypotheses(issue, search_results, evidence, auth_issue)
        form_step = next(step for step in plan.steps if "Form competing" in step.objective)
        form_step.status = StepStatus.COMPLETE
        form_step.notes.append(f"Formed {len(hypotheses)} competing hypothesis/hypotheses")
        for hypothesis in hypotheses:
            self.scorer.evaluate(hypothesis, evidence)
        validate_step = next(step for step in plan.steps if "Validate hypotheses" in step.objective)
        validate_step.status = StepStatus.COMPLETE

        recommendations = [item.recommendation for item in hypotheses if item.recommendation and item.confidence >= 0.5]
        report_step = next(step for step in plan.steps if "recommendations" in step.objective.casefold())
        report_step.status = StepStatus.COMPLETE
        return InvestigationReport(issue, plan, evidence, hypotheses, recommendations, limitations)

    @staticmethod
    def _issue_queries(issue: str) -> list[str]:
        ignored = {"a", "an", "and", "after", "before", "but", "for", "in", "is", "of", "on", "the", "to", "when"}
        words = [word.strip(".,:;!?()[]{}\"'") for word in issue.split()]
        return list(dict.fromkeys(word for word in words if len(word) >= 3 and word.casefold() not in ignored))[:6]

    @staticmethod
    def _matching_evidence(evidence: EvidenceStore, *needles: str) -> list[str]:
        lowered = tuple(item.casefold() for item in needles)
        return [item.id for item in evidence.all() if any(needle in item.observation.casefold() for needle in lowered)]

    def _form_hypotheses(
        self,
        issue: str,
        searches: dict[str, dict[str, Any]],
        evidence: EvidenceStore,
        auth_issue: bool,
    ) -> list[Hypothesis]:
        if not auth_issue:
            related = [item.id for item in evidence.all()]
            return [
                Hypothesis(
                    id="H1",
                    statement=f"The reported behavior is caused by code matched during investigation: {issue}",
                    supporting_evidence=related[:3],
                    recommendation="Reproduce the bug with a focused test, then inspect the highest-relevance matched code path.",
                )
            ]

        refresh_matches = searches.get("refresh", {}).get("matches", [])
        jwt_ids = self._matching_evidence(evidence, "jwt")
        auth_ids = self._matching_evidence(evidence, "authentication", "401")
        hypotheses: list[Hypothesis] = []
        if not refresh_matches:
            missing = evidence.create(
                source_type=SourceType.REPOSITORY,
                observation="A repository-wide search found no refresh-token implementation or refresh endpoint.",
                reliability=0.85,
                relevance=1.0,
            )
            hypotheses.append(
                Hypothesis(
                    id="H1",
                    statement="The 401 occurs because refresh-token creation or handling is not implemented.",
                    supporting_evidence=[missing.id],
                    recommendation="Implement a refresh-token endpoint and tests, or stop clients from attempting token refresh.",
                )
            )
        else:
            hypotheses.append(
                Hypothesis(
                    id="H1",
                    statement="The refresh-token path exists but rejects the supplied token.",
                    supporting_evidence=self._matching_evidence(evidence, "refresh")[:3],
                    recommendation="Trace claims, expiration, token type, and secret through the refresh handler.",
                )
            )
        verification_matches = searches.get("jwt.decode", {}).get("matches", [])
        if not verification_matches:
            missing_verification = evidence.create(
                source_type=SourceType.REPOSITORY,
                observation="A repository-wide search found JWT signing references but no jwt.decode verification call.",
                reliability=0.85,
                relevance=0.9,
            )
            verification_ids = jwt_ids[:1] + [missing_verification.id]
            verification_statement = "JWT tokens are signed, but no JWT verification path is implemented."
            verification_recommendation = "Add JWT decoding and validation for signature, expiry, token type, issuer, and audience."
        else:
            verification_ids = self._matching_evidence(evidence, "jwt.decode")[:3]
            verification_statement = "JWT verification may reject claims or configuration produced by token signing."
            verification_recommendation = "Compare signing and decoding secret, algorithm, issuer, audience, token type, and expiry handling."

        hypotheses.extend(
            [
                Hypothesis(
                    id="H2",
                    statement=verification_statement,
                    supporting_evidence=verification_ids,
                    recommendation=verification_recommendation,
                ),
                Hypothesis(
                    id="H3",
                    statement="The 401 is produced by the login credential check rather than token refresh.",
                    supporting_evidence=auth_ids[:3],
                    recommendation="Add tests that distinguish failed login, expired access token, and failed refresh responses.",
                ),
            ]
        )
        return hypotheses
