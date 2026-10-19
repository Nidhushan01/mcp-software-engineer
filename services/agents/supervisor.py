"""Supervisor nodes: classify, plan, review, route, and synthesize."""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END

from services.investigation.planner import InvestigationPlanner

from .state import AgentState


class SupervisorAgent:
    BUG_TERMS = ("bug", "error", "fail", "broken", "incorrect", "401", "403", "404", "500", "exception", "after")

    def __init__(self) -> None:
        self.planner = InvestigationPlanner()

    async def intake(self, state: AgentState) -> dict:
        request = state["request"].strip()
        kind = "bug_investigation" if any(term in request.casefold() for term in self.BUG_TERMS) else "code_question"
        plan = self.planner.create(request).to_dict()
        return {
            "request_kind": kind,
            "plan": plan,
            "next_agent": "code_analyst",
            "supervisor_notes": [f"Classified request as {kind} and created a {len(plan['steps'])}-step plan."],
        }

    async def review(self, state: AgentState) -> dict:
        notes = list(state["supervisor_notes"])
        trace = list(state["investigation_trace"])
        trace.append({
            "iteration": state["iteration"],
            "evidence_count": len(state["evidence"]),
            "hypothesis_count": len(state["hypotheses"]),
            "evidence_sufficient": state["evidence_sufficient"],
            "evidence_requests": list(state["evidence_requests"]),
        })
        if state["request_kind"] == "code_question":
            notes.append("Code analysis is sufficient; route to synthesis.")
            return {"next_agent": "synthesize", "supervisor_notes": notes, "investigation_trace": trace, "termination_reason": "code analysis complete"}
        if state["evidence_sufficient"]:
            notes.append("Evidence sufficiency threshold met; root cause can be stated with traceable support.")
            return {"next_agent": "synthesize", "supervisor_notes": notes, "investigation_trace": trace, "termination_reason": "evidence sufficient"}
        if state["iteration"] < state["max_iterations"]:
            notes.append(f"More evidence required: {', '.join(state['evidence_requests'])}")
            return {"next_agent": "code_analyst", "supervisor_notes": notes, "investigation_trace": trace}
        notes.append("Evidence-loop limit reached; unresolved hypotheses remain explicitly unverified.")
        return {"next_agent": "synthesize", "supervisor_notes": notes, "investigation_trace": trace, "termination_reason": "iteration limit reached"}

    @staticmethod
    def route_after_review(state: AgentState) -> Literal["code_analyst", "synthesize"]:
        return state["next_agent"]

    @staticmethod
    async def synthesize(state: AgentState) -> dict:
        lines = [f"# Supervisor report: {state['request']}", "", f"Classification: `{state['request_kind']}`", ""]
        lines.extend(["## Investigation plan", ""])
        for step in state["plan"]["steps"]:
            lines.append(f"{step['number']}. {step['objective']}")
        lines.extend(["", "## Evidence", ""])
        for item in state["evidence"]:
            location = item.get("file") or item["source_type"]
            if item.get("line_start"):
                location += f":{item['line_start']}"
            lines.append(f"- **{item['id']}** — `{location}` — {item['observation']}")
        if not state["evidence"]:
            lines.append("- No repository evidence was found.")
        lines.extend(["", "## Ranked hypotheses", ""])
        for item in sorted(state["hypotheses"], key=lambda value: value["confidence"], reverse=True):
            evidence = ", ".join(item["evidence"]) or "none"
            lines.extend(
                [
                    f"### {item['id']}: {item['statement']}",
                    f"- Status: **{item['status']}**",
                    f"- Confidence: **{item['confidence']:.2f}**",
                    f"- Evidence: {evidence}",
                    f"- Recommendation: {item['recommendation']}",
                    "",
                ]
            )
        if state["request_kind"] == "code_question" and not state["hypotheses"]:
            lines.extend(["The evidence above identifies the relevant implementation locations.", ""])
        if state["request_kind"] == "bug_investigation":
            lines.extend(["## Root cause decision", ""])
            if state["evidence_sufficient"]:
                lines.append(f"**Root cause:** {state['root_cause']}")
            else:
                lines.append("**Root cause:** Inconclusive with the evidence collected; no unsupported conclusion was promoted.")
            lines.extend(["", "## Recommendations", ""])
            lines.extend(f"- {item}" for item in state["recommendations"] or ["Collect the outstanding evidence and add a focused reproduction test before changing code."])
            lines.extend(["", "## Investigation loop", ""])
            for cycle in state["investigation_trace"]:
                decision = "enough evidence" if cycle["evidence_sufficient"] else "investigate again"
                lines.append(f"- Iteration {cycle['iteration']}: {cycle['evidence_count']} evidence items, {cycle['hypothesis_count']} hypotheses — **{decision}**")
            lines.extend(["", f"Termination: **{state['termination_reason']}**", ""])
        lines.extend(["## Supervisor review", ""])
        lines.extend(f"- {note}" for note in state["supervisor_notes"])
        return {"final_report": "\n".join(lines).rstrip() + "\n"}
