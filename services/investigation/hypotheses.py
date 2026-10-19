"""Hypothesis model and lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class HypothesisStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    CONFIRMED = "confirmed"


@dataclass
class Hypothesis:
    id: str
    statement: str
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    status: HypothesisStatus = HypothesisStatus.UNVERIFIED
    recommendation: str | None = None
    explicitly_reproduced: bool = False

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.statement.strip():
            raise ValueError("Hypothesis ID and statement cannot be empty")

    def add_support(self, evidence_id: str) -> None:
        if evidence_id not in self.supporting_evidence:
            self.supporting_evidence.append(evidence_id)

    def add_contradiction(self, evidence_id: str) -> None:
        if evidence_id not in self.contradicting_evidence:
            self.contradicting_evidence.append(evidence_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "evidence": self.supporting_evidence,
            "contradicting_evidence": self.contradicting_evidence,
            "confidence": self.confidence,
            "status": self.status.value,
            "recommendation": self.recommendation,
        }
