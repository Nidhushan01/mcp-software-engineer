"""Investigation result model and Markdown rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .evidence import Evidence, EvidenceStore
from .hypotheses import Hypothesis
from .planner import InvestigationPlan


@dataclass
class InvestigationReport:
    issue: str
    plan: InvestigationPlan
    evidence: EvidenceStore
    hypotheses: list[Hypothesis]
    recommendations: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue,
            "plan": self.plan.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence.all()],
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "recommendations": self.recommendations,
            "limitations": self.limitations,
        }

    @staticmethod
    def _location(item: Evidence) -> str:
        if not item.file:
            return item.source_type.value
        location = item.file
        if item.line_start is not None:
            location += f":{item.line_start}"
            if item.line_end != item.line_start:
                location += f"-{item.line_end}"
        if item.symbol:
            location += f" (`{item.symbol}`)"
        return location

    def to_markdown(self) -> str:
        lines = [f"# Investigation report: {self.issue}", "", "## Investigation plan", ""]
        for step in self.plan.steps:
            lines.append(f"{step.number}. [{step.status.value}] {step.objective}")

        lines.extend(["", "## Evidence", ""])
        if not self.evidence.all():
            lines.append("No evidence was collected.")
        for item in self.evidence.all():
            lines.extend(
                [
                    f"### {item.id}",
                    "",
                    f"- Source: {item.source_type.value}",
                    f"- Location: {self._location(item)}",
                    f"- Observation: {item.observation}",
                    f"- Quality: {item.quality:.2f}",
                    "",
                ]
            )

        lines.extend(["## Hypotheses", ""])
        for item in sorted(self.hypotheses, key=lambda value: value.confidence, reverse=True):
            evidence_ids = ", ".join(item.supporting_evidence) or "none"
            contradictions = ", ".join(item.contradicting_evidence) or "none"
            lines.extend(
                [
                    f"### {item.id}: {item.statement}",
                    "",
                    f"- Status: **{item.status.value}**",
                    f"- Confidence: **{item.confidence:.2f}**",
                    f"- Supporting evidence: {evidence_ids}",
                    f"- Contradicting evidence: {contradictions}",
                ]
            )
            if item.recommendation:
                lines.append(f"- Recommendation: {item.recommendation}")
            lines.append("")

        lines.extend(["## Recommendations", ""])
        lines.extend(f"- {item}" for item in self.recommendations or ["Collect more evidence before changing code."])
        if self.limitations:
            lines.extend(["", "## Limitations", ""])
            lines.extend(f"- {item}" for item in self.limitations)
        return "\n".join(lines).rstrip() + "\n"
