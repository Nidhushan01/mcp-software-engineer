"""Bug specialist that challenges and ranks evidence-backed hypotheses."""

from __future__ import annotations

from services.investigation.confidence import ConfidenceScorer
from services.investigation.evidence import EvidenceStore, SourceType
from services.investigation.hypotheses import Hypothesis

from .state import AgentState


class BugInvestigatorAgent:
    def __init__(self) -> None:
        self.scorer = ConfidenceScorer()

    @staticmethod
    def _store(state: AgentState) -> EvidenceStore:
        store = EvidenceStore()
        for raw in state["evidence"]:
            values = dict(raw)
            values.pop("quality", None)
            values.pop("id", None)
            values["source_type"] = SourceType(values["source_type"])
            store.create(**values)
        return store

    @staticmethod
    def _ids(store: EvidenceStore, *terms: str) -> list[str]:
        needles = tuple(term.casefold() for term in terms)
        return [item.id for item in store.all() if any(term in item.observation.casefold() for term in needles)]

    async def investigate(self, state: AgentState) -> dict:
        store = self._store(state)
        observations = "\n".join(item.observation.casefold() for item in store.all())
        auth_issue = any(term in state["request"].casefold() for term in ("login", "auth", "401", "token", "jwt"))

        required: list[str] = []
        if auth_issue:
            for query in ("authentication", "JWT", "jwt.decode"):
                marker = f"{query.casefold()!r}"
                if marker not in observations:
                    required.append(query)
        if required:
            return {
                "evidence_requests": required,
                "hypotheses": state["hypotheses"],
                "evidence_sufficient": False,
                "root_cause": "",
                "recommendations": [],
            }

        candidates: list[Hypothesis] = []
        if auth_issue:
            refresh_absence = self._ids(store, "no matches for 'refresh'")
            refresh_expectation = self._ids(store, "documentation states near 'refresh'")
            jwt_signing = self._ids(store, "jwt_secret", "jwt.encode")
            verification_absence = self._ids(store, "no matches for 'jwt.decode'")
            verification_expectation = self._ids(store, "pyjwt documentation reference")
            login_401 = self._ids(store, "401", "invalid credentials")
            candidates = [
                Hypothesis(
                    "H1",
                    "Refresh-token creation or handling is absent.",
                    supporting_evidence=(refresh_absence[:1] + refresh_expectation[:2]),
                    recommendation="Implement and test refresh-token issuance/validation, or stop clients from calling refresh.",
                ),
                Hypothesis(
                    "H2",
                    "Tokens are signed, but no JWT verification path is implemented.",
                    supporting_evidence=(jwt_signing[:1] + verification_absence[:1] + verification_expectation[:1]),
                    recommendation="Add JWT decode validation for signature, expiry, token type, issuer, and audience.",
                ),
                Hypothesis(
                    "H3",
                    "The observed 401 originates in the login credential check, not a refresh handler.",
                    supporting_evidence=login_401[:2],
                    recommendation="Add separate tests for login failure, access-token expiry, and refresh failure.",
                ),
            ]
        else:
            candidates = [
                Hypothesis(
                    "H1",
                    f"The reported behavior is associated with the inspected implementation for: {state['request']}",
                    supporting_evidence=[item.id for item in store.all()[:3]],
                    recommendation="Add a focused reproduction test before changing the highest-relevance code path.",
                )
            ]

        # Reject candidates that have no direct supporting or contradicting evidence.
        ranked: list[Hypothesis] = []
        for hypothesis in candidates:
            if not hypothesis.supporting_evidence and not hypothesis.contradicting_evidence:
                continue
            self.scorer.evaluate(hypothesis, store)
            ranked.append(hypothesis)
        ranked.sort(key=lambda item: item.confidence, reverse=True)
        supported = [item for item in ranked if item.status.value in {"supported", "confirmed"}]
        strongest = supported[0] if supported else None
        sufficient = strongest is not None and strongest.confidence >= 0.65 and len(strongest.supporting_evidence) >= 2
        requests = [] if sufficient else [
            f"validate {item.statement}" for item in ranked[:2]
            if item.status.value in {"unverified", "supported"}
        ]
        if not sufficient and not requests:
            requests = ["reproduction test or direct implementation evidence"]
        return {
            "hypotheses": [item.to_dict() for item in ranked],
            "evidence_requests": requests,
            "evidence_sufficient": sufficient,
            "root_cause": strongest.statement if sufficient else "",
            "recommendations": [strongest.recommendation] if sufficient and strongest.recommendation else [],
        }
