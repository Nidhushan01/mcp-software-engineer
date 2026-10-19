from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConnectRepositoryRequest(BaseModel):
    path: str
    name: str | None = None


class RepositoryResponse(BaseModel):
    id: str
    name: str
    path: str
    connected_at: datetime


class CreateInvestigationRequest(BaseModel):
    repository_id: str
    issue: str = Field(min_length=1)
    max_iterations: int = Field(default=3, ge=1, le=10)
    use_knowledge: bool = True
    github_repository: str | None = Field(default=None, pattern=r"^[^/]+/[^/]+$")


class InvestigationResponse(BaseModel):
    id: str
    repository_id: str
    issue: str
    status: Literal["queued", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    termination_reason: str | None = None
    evidence_sufficient: bool | None = None
    root_cause: str | None = None
    report: str | None = None
    error: str | None = None


class PatchProposalRequest(BaseModel):
    path: str
    new_content: str
    require_confirmed: bool = True


class PatchResponse(BaseModel):
    status: str
    proposal_id: str | None = None
    path: str | None = None
    diff: str | None = None
    validation: dict[str, Any] | None = None
    feedback: str | None = None
    apply_result: dict[str, Any] | None = None


class ChangeRequest(BaseModel):
    feedback: str = Field(min_length=1)
