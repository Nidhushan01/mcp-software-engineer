"""Transparent confidence scoring for hypotheses."""

from __future__ import annotations

from math import prod

from .evidence import EvidenceStore
from .hypotheses import Hypothesis, HypothesisStatus


class ConfidenceScorer:
    """Combine independent evidence without treating confidence as certainty."""

    def score(self, hypothesis: Hypothesis, evidence: EvidenceStore) -> float:
        supporting = [evidence.get(item).quality for item in hypothesis.supporting_evidence]
        contradicting = [evidence.get(item).quality for item in hypothesis.contradicting_evidence]
        support = 1 - prod(1 - value for value in supporting) if supporting else 0.0
        contradiction = 1 - prod(1 - value for value in contradicting) if contradicting else 0.0
        confidence = max(0.0, min(1.0, 0.20 + 0.75 * support - 0.80 * contradiction))
        if not hypothesis.explicitly_reproduced:
            confidence = min(confidence, 0.89)
        return round(confidence, 2)

    def evaluate(self, hypothesis: Hypothesis, evidence: EvidenceStore) -> Hypothesis:
        hypothesis.confidence = self.score(hypothesis, evidence)
        if not hypothesis.supporting_evidence and not hypothesis.contradicting_evidence:
            hypothesis.status = HypothesisStatus.UNVERIFIED
        elif hypothesis.contradicting_evidence and hypothesis.confidence < 0.5:
            hypothesis.status = HypothesisStatus.CONTRADICTED
        elif hypothesis.explicitly_reproduced:
            hypothesis.status = HypothesisStatus.CONFIRMED
        elif hypothesis.confidence >= 0.5:
            hypothesis.status = HypothesisStatus.SUPPORTED
        else:
            hypothesis.status = HypothesisStatus.UNVERIFIED
        return hypothesis
