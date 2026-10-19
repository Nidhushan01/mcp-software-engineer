"""Evidence records and provenance validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Iterable


class SourceType(StrEnum):
    REPOSITORY = "repository"
    GIT = "git"
    GITHUB = "github"
    DOCUMENTATION = "documentation"
    TEST = "test"
    DEPENDENCY = "dependency"
    USER = "user"


@dataclass(frozen=True)
class Evidence:
    id: str
    source_type: SourceType
    observation: str
    file: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    symbol: str | None = None
    reliability: float = 1.0
    relevance: float = 1.0

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Evidence ID cannot be empty")
        if not self.observation.strip():
            raise ValueError("Evidence observation cannot be empty")
        if not 0 <= self.reliability <= 1 or not 0 <= self.relevance <= 1:
            raise ValueError("Evidence reliability and relevance must be between 0 and 1")
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError("Both line_start and line_end must be provided together")
        if self.line_start is not None:
            if self.file is None:
                raise ValueError("Line evidence must include a file")
            if self.line_start < 1 or self.line_end < self.line_start:
                raise ValueError("Invalid evidence line range")

    @property
    def quality(self) -> float:
        return self.reliability * self.relevance

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source_type"] = self.source_type.value
        result["quality"] = round(self.quality, 4)
        return result


class EvidenceStore:
    """Append-only evidence collection with stable IDs."""

    def __init__(self, evidence: Iterable[Evidence] = ()) -> None:
        self._items: dict[str, Evidence] = {}
        for item in evidence:
            self.add(item)

    def add(self, evidence: Evidence) -> Evidence:
        if evidence.id in self._items:
            raise ValueError(f"Duplicate evidence ID: {evidence.id}")
        self._items[evidence.id] = evidence
        return evidence

    def create(self, **values: Any) -> Evidence:
        evidence = Evidence(id=f"E{len(self._items) + 1}", **values)
        return self.add(evidence)

    def get(self, evidence_id: str) -> Evidence:
        try:
            return self._items[evidence_id]
        except KeyError as exc:
            raise KeyError(f"Unknown evidence ID: {evidence_id}") from exc

    def all(self) -> list[Evidence]:
        return list(self._items.values())
