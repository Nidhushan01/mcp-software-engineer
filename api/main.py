from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from mcp_clients.manager import MCPManager
from mcp_clients.registry import DEFAULT_KNOWLEDGE_ROOT, PROJECT_ROOT, create_agent_registry
from services.agents import RepositoryAgentGraph

from .models import ChangeRequest, ConnectRepositoryRequest, CreateInvestigationRequest, InvestigationResponse, PatchProposalRequest, PatchResponse, RepositoryResponse
from .store import APIStore, InvestigationRecord, PatchRuntime, RepositoryRecord, now


store = APIStore()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await store.close()


app = FastAPI(title="Evidence-Driven Repository Investigator", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _allowed_root() -> Path:
    return Path(os.getenv("REPOSITORY_ALLOWED_ROOT", str(PROJECT_ROOT))).resolve()


def _safe_repository(path: str) -> Path:
    candidate = Path(path)
    resolved = (PROJECT_ROOT / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    try:
        resolved.relative_to(_allowed_root())
    except ValueError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Repository path is outside REPOSITORY_ALLOWED_ROOT") from exc
    if not resolved.is_dir():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Repository path is not a directory")
    return resolved


def _repository(repository_id: str) -> RepositoryRecord:
    record = store.repositories.get(repository_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Repository not found")
    return record


def _investigation(investigation_id: str) -> InvestigationRecord:
    record = store.investigations.get(investigation_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    return record


def _investigation_response(record: InvestigationRecord) -> InvestigationResponse:
    state = record.state or {}
    return InvestigationResponse(
        id=record.id, repository_id=record.repository_id, issue=record.issue,
        status=record.status, created_at=record.created_at, updated_at=record.updated_at,
        termination_reason=state.get("termination_reason"), evidence_sufficient=state.get("evidence_sufficient"),
        root_cause=state.get("root_cause"), report=state.get("final_report"), error=record.error,
    )


async def _run_investigation(record: InvestigationRecord, request: CreateInvestigationRequest) -> None:
    repository = _repository(record.repository_id)
    lock = store.repository_locks.setdefault(repository.id, asyncio.Lock())
    async with lock:
        record.status, record.updated_at = "running", now()
        try:
            github = request.github_repository
            registry = create_agent_registry(
                repository.path,
                include_github=bool(github),
                knowledge_root=DEFAULT_KNOWLEDGE_ROOT if request.use_knowledge else None,
            )
            async with MCPManager(registry) as manager:
                owner, repo = github.split("/", 1) if github else (None, None)
                record.state = await RepositoryAgentGraph(manager).run(
                    record.issue, request.max_iterations, github_owner=owner, github_repo=repo,
                )
            record.status = "completed"
        except Exception as exc:
            record.status, record.error = "failed", str(exc)
        finally:
            record.updated_at = now()


@app.post("/repositories/connect", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def connect_repository(request: ConnectRepositoryRequest) -> RepositoryResponse:
    path = _safe_repository(request.path)
    existing = next((item for item in store.repositories.values() if item.path == path), None)
    if existing:
        return RepositoryResponse(id=existing.id, name=existing.name, path=str(existing.path), connected_at=existing.connected_at)
    record = RepositoryRecord(uuid.uuid4().hex, request.name or path.name, path)
    store.repositories[record.id] = record
    return RepositoryResponse(id=record.id, name=record.name, path=str(record.path), connected_at=record.connected_at)


@app.post("/investigations", response_model=InvestigationResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_investigation(request: CreateInvestigationRequest) -> InvestigationResponse:
    _repository(request.repository_id)
    record = InvestigationRecord(uuid.uuid4().hex, request.repository_id, request.issue.strip())
    store.investigations[record.id] = record
    task = asyncio.create_task(_run_investigation(record, request))
    store.tasks.add(task)
    task.add_done_callback(store.tasks.discard)
    return _investigation_response(record)


@app.get("/investigations/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: str) -> InvestigationResponse:
    return _investigation_response(_investigation(investigation_id))


@app.get("/investigations/{investigation_id}/evidence")
async def get_evidence(investigation_id: str) -> dict[str, Any]:
    record = _investigation(investigation_id)
    return {"investigation_id": record.id, "evidence": (record.state or {}).get("evidence", [])}


@app.get("/investigations/{investigation_id}/hypotheses")
async def get_hypotheses(investigation_id: str) -> dict[str, Any]:
    record = _investigation(investigation_id)
    return {"investigation_id": record.id, "hypotheses": (record.state or {}).get("hypotheses", [])}


@app.get("/investigations/{investigation_id}/patch", response_model=PatchResponse)
async def get_patch(investigation_id: str) -> PatchResponse:
    record = _investigation(investigation_id)
    if record.patch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No patch has been proposed")
    return PatchResponse(**record.patch)


@app.post("/investigations/{investigation_id}/patch", response_model=PatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def propose_patch(investigation_id: str, request: PatchProposalRequest) -> PatchResponse:
    record = _investigation(investigation_id)
    if record.status != "completed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Investigation must complete before proposing a patch")
    hypotheses = (record.state or {}).get("hypotheses", [])
    confirmed = any(item.get("status") == "confirmed" for item in hypotheses)
    if request.require_confirmed and not confirmed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Patch generation requires a confirmed hypothesis")
    if investigation_id in store.patch_runtimes:
        raise HTTPException(status.HTTP_409_CONFLICT, "A patch proposal is already awaiting a decision")
    repository = _repository(record.repository_id)
    runtime = PatchRuntime(repository.path, uuid.uuid4().hex)
    await runtime.start()
    try:
        result = await runtime.call("propose", request.path, request.new_content)
        interrupt_value = result["__interrupt__"][0].value
        patch = {
            "status": "waiting_for_approval", "proposal_id": interrupt_value["proposal_id"],
            "path": request.path, "diff": interrupt_value["diff"], "validation": interrupt_value["validation"],
        }
        record.patch = patch
        store.patch_runtimes[investigation_id] = runtime
        return PatchResponse(**patch)
    except BaseException:
        await runtime.close()
        raise


async def _decide_patch(investigation_id: str, decision: str, feedback: str = "") -> PatchResponse:
    record = _investigation(investigation_id)
    runtime = store.patch_runtimes.get(investigation_id)
    if runtime is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "No patch is waiting for approval")
    try:
        result = await runtime.call("resume", decision, feedback)
        record.patch = {
            **(record.patch or {}), "status": result["approval_status"], "feedback": result.get("feedback") or None,
            "apply_result": result.get("apply_result") or None,
        }
        return PatchResponse(**record.patch)
    finally:
        store.patch_runtimes.pop(investigation_id, None)
        await runtime.close()


@app.post("/investigations/{investigation_id}/approve", response_model=PatchResponse)
async def approve_patch(investigation_id: str) -> PatchResponse:
    return await _decide_patch(investigation_id, "approve")


@app.post("/investigations/{investigation_id}/reject", response_model=PatchResponse)
async def reject_patch(investigation_id: str) -> PatchResponse:
    return await _decide_patch(investigation_id, "reject")


@app.post("/investigations/{investigation_id}/request-changes", response_model=PatchResponse)
async def request_patch_changes(investigation_id: str, request: ChangeRequest) -> PatchResponse:
    return await _decide_patch(investigation_id, "request_changes", request.feedback)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
