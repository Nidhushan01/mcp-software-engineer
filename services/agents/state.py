"""Serializable shared state for the supervisor graph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


RequestKind = Literal["code_question", "bug_investigation"]
AgentName = Literal["code_analyst", "bug_investigator", "synthesize"]


class AgentState(TypedDict):
    request: str
    request_kind: RequestKind
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    inspected_files: list[str]
    github_owner: str
    github_repo: str
    github_enabled: bool
    github_searched: bool
    knowledge_enabled: bool
    documentation_searched: bool
    hypotheses: list[dict[str, Any]]
    evidence_requests: list[str]
    evidence_sufficient: bool
    root_cause: str
    recommendations: list[str]
    investigation_trace: list[dict[str, Any]]
    termination_reason: str
    iteration: int
    max_iterations: int
    next_agent: AgentName
    supervisor_notes: list[str]
    final_report: str
