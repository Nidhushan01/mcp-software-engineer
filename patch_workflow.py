"""CLI for propose-first, human-approved repository patching."""

from __future__ import annotations

import argparse
import asyncio
import uuid
from pathlib import Path

from mcp_clients.manager import MCPManager
from mcp_clients.registry import MCPRegistry, create_patch_config
from services.agents import PatchApprovalWorkflow


async def run(path: str, content_file: Path, repository: Path) -> None:
    registry = MCPRegistry()
    registry.register(create_patch_config(repository))
    async with MCPManager(registry) as manager:
        workflow = PatchApprovalWorkflow(manager)
        thread_id = uuid.uuid4().hex
        result = await workflow.propose(path, content_file.read_text(encoding="utf-8"), thread_id)
        interrupts = result.get("__interrupt__", ())
        if not interrupts:
            print(result)
            return
        request = interrupts[0].value
        print(request["diff"])
        print("\nStatus: WAITING_FOR_APPROVAL")
        answer = input("Decision [approve/reject/request_changes]: ").strip().casefold()
        if answer not in {"approve", "reject", "request_changes"}:
            answer = "reject"
        feedback = input("Feedback (optional): ").strip() if answer == "request_changes" else ""
        final = await workflow.resume(thread_id, answer, feedback)  # type: ignore[arg-type]
        print(f"Patch status: {final['approval_status']}")
        if feedback:
            print(f"Requested changes: {feedback}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Propose, review, and optionally apply one repository patch")
    parser.add_argument("path", help="Repository-relative target file")
    parser.add_argument("--content-file", type=Path, required=True, help="File containing the proposed complete content")
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.path, args.content_file.resolve(), args.repository.resolve()))


if __name__ == "__main__":
    main()
