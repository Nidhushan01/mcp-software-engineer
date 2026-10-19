"""Patch proposal agent and human-in-the-loop approval workflow."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from mcp_clients.manager import MCPManager


Decision = Literal["approve", "reject", "request_changes"]


class PatchState(TypedDict):
    path: str
    new_content: str
    proposal_id: str
    diff: str
    validation: dict[str, Any]
    approval_status: str
    feedback: str
    apply_result: dict[str, Any]


class PatchAgent:
    def __init__(self, manager: MCPManager) -> None:
        self.manager = manager

    async def propose(self, state: PatchState) -> dict[str, Any]:
        proposal = await self.manager.call_tool("patch", "generate_diff", {
            "path": state["path"], "new_content": state["new_content"],
        })
        validation = await self.manager.call_tool("patch", "validate_patch", {
            "proposal_id": proposal["proposal_id"],
        })
        if not validation["valid"]:
            return {
                "proposal_id": proposal["proposal_id"], "diff": proposal["diff"],
                "validation": validation, "approval_status": "validation_failed",
            }
        return {
            "proposal_id": proposal["proposal_id"], "diff": proposal["diff"],
            "validation": validation, "approval_status": "waiting_for_approval",
        }

    @staticmethod
    def request_approval(state: PatchState) -> dict[str, Any]:
        if state["approval_status"] == "validation_failed":
            return {}
        response = interrupt({
            "status": "WAITING_FOR_APPROVAL",
            "proposal_id": state["proposal_id"],
            "diff": state["diff"],
            "validation": state["validation"],
            "allowed_decisions": ["approve", "reject", "request_changes"],
        })
        if not isinstance(response, dict) or response.get("decision") not in {"approve", "reject", "request_changes"}:
            raise ValueError("Resume with decision: approve, reject, or request_changes")
        return {
            "approval_status": response["decision"],
            "feedback": str(response.get("feedback", "")),
        }

    async def apply(self, state: PatchState) -> dict[str, Any]:
        result = await self.manager.call_tool("patch", "apply_patch", {
            "proposal_id": state["proposal_id"],
            "approval": f"APPROVE {state['proposal_id']}",
        })
        return {"approval_status": "applied", "apply_result": result}


class PatchApprovalWorkflow:
    """Proposal stops at interrupt; only an explicit resume can reach apply."""

    def __init__(self, manager: MCPManager) -> None:
        if not manager.has_server("patch"):
            raise RuntimeError("Patch MCP server is not connected")
        agent = PatchAgent(manager)
        builder = StateGraph(PatchState)
        builder.add_node("propose", agent.propose)
        builder.add_node("human_approval", agent.request_approval)
        builder.add_node("apply", agent.apply)
        builder.add_edge(START, "propose")
        builder.add_edge("propose", "human_approval")
        builder.add_conditional_edges("human_approval", self._route, {"apply": "apply", "stop": END})
        builder.add_edge("apply", END)
        self.graph = builder.compile(checkpointer=InMemorySaver())

    @staticmethod
    def _route(state: PatchState) -> Literal["apply", "stop"]:
        return "apply" if state["approval_status"] == "approve" else "stop"

    @staticmethod
    def _config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    async def propose(self, path: str, new_content: str, thread_id: str) -> dict[str, Any]:
        initial: PatchState = {
            "path": path, "new_content": new_content, "proposal_id": "", "diff": "",
            "validation": {}, "approval_status": "", "feedback": "", "apply_result": {},
        }
        return await self.graph.ainvoke(initial, self._config(thread_id))

    async def resume(self, thread_id: str, decision: Decision, feedback: str = "") -> dict[str, Any]:
        return await self.graph.ainvoke(Command(resume={"decision": decision, "feedback": feedback}), self._config(thread_id))
