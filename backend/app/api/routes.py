"""FastAPI route definitions."""
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.schemas.watch import CreateWatchRequest, WatchRunSummary
from app.schemas.evidence import EvidenceBundleResponse
from app.services.watch_service import WatchService
from app.services.evidence_service import EvidenceService
from app.services.orchestrator import OrchestratorEngine

router = APIRouter(prefix="/api", tags=["api"])

# Default org for single-tenant; in production use auth.uid() -> user -> organization_id
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"


def _watch_to_response(watch: Dict[str, Any], total_runs: int = 0, total_changes: int = 0) -> dict:
    return {
        "id": str(watch["id"]),
        "name": watch["name"],
        "description": watch.get("description"),
        "status": watch.get("status", "active"),
        "next_run_at": watch.get("next_run_at"),
        "total_runs": total_runs,
        "total_changes": total_changes,
        "config": watch.get("config"),
        "schedule": watch.get("schedule"),
        "created_at": watch.get("created_at"),
        "last_run_at": watch.get("last_run_at"),
    }


@router.post("/watches", response_model=dict)
async def create_watch(request: CreateWatchRequest):
    """Create a new compliance watch."""
    svc = WatchService()
    watch = await svc.create_watch(
        organization_id=DEFAULT_ORG_ID,
        name=request.name,
        description=request.description,
        watch_type=request.type,
        config=request.config,
        integrations=request.integrations,
    )
    return _watch_to_response(watch)


@router.get("/watches", response_model=List[dict])
async def list_watches():
    """List all watches for the organization."""
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    result = []
    for w in watches:
        runs = await svc.get_watch_runs(str(w["id"]), limit=1000)
        changes_count = 0
        for r in runs:
            changes_count += r.get("changes_detected") or 0
        result.append(_watch_to_response(w, total_runs=len(runs), total_changes=changes_count))
    return result


@router.get("/watches/{watch_id}", response_model=dict)
async def get_watch(watch_id: str):
    """Get a single watch."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    runs = await svc.get_watch_runs(watch_id, limit=1000)
    changes_count = sum((r.get("changes_detected") or 0) for r in runs)
    return _watch_to_response(watch, total_runs=len(runs), total_changes=changes_count)


@router.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, background_tasks: BackgroundTasks):
    """Trigger immediate watch execution (queued in background)."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    background_tasks.add_task(_execute_watch_background, watch_id)
    return {"status": "queued", "watch_id": watch_id, "message": "Watch execution started"}


async def _execute_watch_background(watch_id: str):
    orchestrator = OrchestratorEngine()
    await orchestrator.execute_watch(watch_id)


@router.get("/watches/{watch_id}/history", response_model=dict)
async def get_watch_history(watch_id: str, limit: int = 50, offset: int = 0):
    """Get watch execution history."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    runs = await svc.get_watch_runs(watch_id, limit=limit, offset=offset)
    return {
        "watch_id": watch_id,
        "runs": [WatchRunSummary(
            id=str(r["id"]),
            watch_id=str(r["watch_id"]),
            status=r["status"],
            started_at=r["started_at"],
            completed_at=r.get("completed_at"),
            duration_ms=r.get("duration_ms"),
            tasks_executed=r.get("tasks_executed", 0),
            tasks_failed=r.get("tasks_failed", 0),
            changes_detected=r.get("changes_detected", 0),
            error_message=r.get("error_message"),
        ).model_dump() for r in runs],
        "total": len(runs),
    }


@router.get("/evidence/{bundle_id}", response_model=dict)
async def get_evidence_bundle(bundle_id: str):
    """Get evidence bundle by ID (with refreshed URLs if applicable)."""
    ev = EvidenceService()
    bundle = await ev.get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    bundle = await ev.refresh_urls(bundle)
    return bundle


@router.get("/runs/recent")
async def recent_runs(limit: int = 50):
    """Recent runs across all watches for the org."""
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    runs: List[Dict[str, Any]] = []
    for w in watches:
        r = await svc.get_watch_runs(str(w["id"]), limit=5)
        for x in r:
            x["watch_name"] = w.get("name")
            runs.append(x)
    runs.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return {"runs": runs[:limit]}


@router.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}
