"""Create explicit, auditable bug-investigation plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class InvestigationStep:
    number: int
    objective: str
    suggested_tools: tuple[str, ...]
    status: StepStatus = StepStatus.PENDING
    notes: list[str] = field(default_factory=list)


@dataclass
class InvestigationPlan:
    issue: str
    steps: list[InvestigationStep]

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue": self.issue,
            "steps": [
                {
                    "number": step.number,
                    "objective": step.objective,
                    "suggested_tools": list(step.suggested_tools),
                    "status": step.status.value,
                    "notes": step.notes,
                }
                for step in self.steps
            ],
        }


class InvestigationPlanner:
    """Produce a domain-aware plan while keeping mandatory verification stages."""

    def create(self, issue: str) -> InvestigationPlan:
        if not issue or not issue.strip():
            raise ValueError("Issue cannot be empty")
        lowered = issue.casefold()
        steps: list[tuple[str, tuple[str, ...]]] = []
        if any(term in lowered for term in ("login", "auth", "401", "token", "jwt")):
            steps.extend(
                [
                    ("Locate authentication endpoints", ("find_files", "search_code")),
                    ("Locate access-token creation", ("find_symbol", "search_code")),
                    ("Locate refresh-token creation", ("search_code", "find_symbol")),
                    ("Locate JWT verification", ("search_code", "search_imports")),
                    ("Inspect authentication configuration", ("find_files", "read_file")),
                ]
            )
        else:
            steps.extend(
                [
                    ("Map the relevant repository area", ("get_repository_structure", "find_files")),
                    ("Locate code related to the reported behavior", ("search_code", "find_symbol")),
                    ("Inspect implementations and configuration", ("read_file", "get_file_metadata")),
                ]
            )
        steps.extend(
            [
                ("Inspect relevant tests", ("find_files", "search_code", "read_file")),
                ("Inspect recent changes", ("git_log", "git_diff", "git_blame")),
                ("Form competing hypotheses", ()),
                ("Validate hypotheses against evidence", ()),
                ("Produce evidence-backed recommendations", ()),
            ]
        )
        return InvestigationPlan(
            issue=issue.strip(),
            steps=[InvestigationStep(number=index, objective=objective, suggested_tools=tools) for index, (objective, tools) in enumerate(steps, 1)],
        )
