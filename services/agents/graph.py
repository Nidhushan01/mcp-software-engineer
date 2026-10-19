"""Compile and run the supervisor multi-agent LangGraph."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph

from mcp_clients.manager import MCPManager

from .bug_investigator import BugInvestigatorAgent
from .code_analyst import CodeAnalystAgent
from .github_agent import GitHubHistoryAgent
from .documentation_agent import DocumentationAgent
from .state import AgentState
from .supervisor import SupervisorAgent


class RepositoryAgentGraph:
    def __init__(self, manager: MCPManager) -> None:
        self.supervisor = SupervisorAgent()
        self.code_analyst = CodeAnalystAgent(manager)
        self.bug_investigator = BugInvestigatorAgent()
        self.github_agent = GitHubHistoryAgent(manager)
        self.documentation_agent = DocumentationAgent(manager)
        self.manager = manager
        self.graph = self._build()

    @staticmethod
    def _after_analysis(state: AgentState) -> Literal["documentation", "github_history", "bug_investigator", "supervisor_review"]:
        if state["request_kind"] == "code_question":
            return "supervisor_review"
        if state["knowledge_enabled"]:
            return "documentation"
        if state["github_enabled"]:
            return "github_history"
        return "bug_investigator"

    @staticmethod
    def _after_documentation(state: AgentState) -> Literal["github_history", "bug_investigator"]:
        return "github_history" if state["github_enabled"] else "bug_investigator"

    def _build(self):
        builder = StateGraph(AgentState)
        builder.add_node("supervisor_intake", self.supervisor.intake)
        builder.add_node("code_analyst", self.code_analyst.analyze)
        builder.add_node("bug_investigator", self.bug_investigator.investigate)
        builder.add_node("github_history", self.github_agent.research)
        builder.add_node("documentation", self.documentation_agent.research)
        builder.add_node("supervisor_review", self.supervisor.review)
        builder.add_node("synthesize", self.supervisor.synthesize)

        builder.add_edge(START, "supervisor_intake")
        builder.add_edge("supervisor_intake", "code_analyst")
        builder.add_conditional_edges(
            "code_analyst",
            self._after_analysis,
            {
                "github_history": "github_history",
                "documentation": "documentation",
                "bug_investigator": "bug_investigator",
                "supervisor_review": "supervisor_review",
            },
        )
        builder.add_conditional_edges(
            "documentation",
            self._after_documentation,
            {"github_history": "github_history", "bug_investigator": "bug_investigator"},
        )
        builder.add_edge("github_history", "bug_investigator")
        builder.add_edge("bug_investigator", "supervisor_review")
        builder.add_conditional_edges(
            "supervisor_review",
            self.supervisor.route_after_review,
            {"code_analyst": "code_analyst", "synthesize": "synthesize"},
        )
        builder.add_edge("synthesize", END)
        return builder.compile()

    async def run(
        self,
        request: str,
        max_iterations: int = 3,
        *,
        github_owner: str | None = None,
        github_repo: str | None = None,
    ) -> AgentState:
        if not request.strip():
            raise ValueError("Request cannot be empty")
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if (github_owner is None) != (github_repo is None):
            raise ValueError("github_owner and github_repo must be provided together")
        github_enabled = github_owner is not None
        if github_enabled and not self.code_analyst.manager.has_server("github"):
            raise RuntimeError("GitHub repository was requested but the GitHub MCP server is not connected")
        initial: AgentState = {
            "request": request.strip(),
            "request_kind": "code_question",
            "plan": {},
            "evidence": [],
            "inspected_files": [],
            "github_owner": github_owner or "",
            "github_repo": github_repo or "",
            "github_enabled": github_enabled,
            "github_searched": False,
            "knowledge_enabled": self.manager.has_server("knowledge"),
            "documentation_searched": False,
            "hypotheses": [],
            "evidence_requests": [],
            "evidence_sufficient": False,
            "root_cause": "",
            "recommendations": [],
            "investigation_trace": [],
            "termination_reason": "",
            "iteration": 0,
            "max_iterations": max_iterations,
            "next_agent": "code_analyst",
            "supervisor_notes": [],
            "final_report": "",
        }
        return await self.graph.ainvoke(initial)
