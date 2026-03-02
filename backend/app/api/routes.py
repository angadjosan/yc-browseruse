"""FastAPI route definitions — all endpoints require authentication."""
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth import AuthContext, get_current_user, require_role
from app.schemas.watch import CreateWatchRequest, WatchRunSummary
from app.schemas.evidence import EvidenceBundleResponse
from app.services.watch_service import WatchService
from app.services.evidence_service import EvidenceService
from app.queue import enqueue_job, set_analysis_status, get_analysis_status
from app.serializers import (
    serialize_watch,
    serialize_change_event,
    serialize_run,
    serialize_run_lean,
    serialize_globe_points,
)

router = APIRouter(prefix="/api", tags=["api"])


class AnalyzeProductRequest(BaseModel):
    """Request to analyze a product URL and create compliance watches."""
    product_url: str


# ── Product analysis (onboarding) ───────────────────────────────────────────

@router.post("/analyze-product", response_model=dict)
async def analyze_product(request: AnalyzeProductRequest, auth: AuthContext = Depends(get_current_user)):
    """Analyze a product URL and create compliance risk watches (runs via worker).

    Returns immediately with a job_id. Poll GET /api/analyze-product/{job_id} for status.
    """
    job_id = str(uuid.uuid4())
    set_analysis_status(job_id, {
        "status": "pending",
        "product_url": request.product_url,
        "organization_id": auth.organization_id,
    })
    enqueue_job("analyze_product", {
        "job_id": job_id,
        "product_url": request.product_url,
        "organization_id": auth.organization_id,
    })
    return {
        "status": "queued",
        "job_id": job_id,
        "product_url": request.product_url,
        "message": "Analysis started. Poll GET /api/analyze-product/{job_id} for status.",
    }


@router.get("/analyze-product/{job_id}", response_model=dict)
async def get_analysis_job_status(job_id: str, auth: AuthContext = Depends(get_current_user)):
    """Get the status of a product analysis job."""
    job = get_analysis_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    # Verify the job belongs to this org
    if job.get("organization_id") and job["organization_id"] != auth.organization_id:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"job_id": job_id, **job}


# ── Watches ─────────────────────────────────────────────────────────────────

@router.post("/watches", response_model=dict)
async def create_watch(request: CreateWatchRequest, auth: AuthContext = Depends(get_current_user)):
    """Create a new compliance watch."""
    svc = WatchService()
    watch = await svc.create_watch(
        organization_id=auth.organization_id,
        name=request.name,
        description=request.description,
        watch_type=request.type,
        config=request.config,
        integrations=request.integrations,
        created_by=auth.user_id,
    )
    return serialize_watch(watch)


@router.get("/watches", response_model=List[dict])
async def list_watches(auth: AuthContext = Depends(get_current_user)):
    """List all watches for the organization — returns frontend Watch[] shape."""
    from app.db import get_supabase
    svc = WatchService()
    watches = await svc.list_watches(auth.organization_id)
    db = get_supabase()

    result = []
    for w in watches:
        wid = str(w["id"])
        runs_r = await asyncio.to_thread(
            lambda wid=wid: db.table("watch_runs").select("id", count="exact").eq("watch_id", wid).execute()
        )
        total_runs = runs_r.count if runs_r.count is not None else len(runs_r.data or [])

        changes_r = await asyncio.to_thread(
            lambda wid=wid: db.table("changes").select("id", count="exact").eq("watch_id", wid).execute()
        )
        total_changes = changes_r.count if changes_r.count is not None else len(changes_r.data or [])

        serialized = serialize_watch(w)
        serialized["totalRuns"] = total_runs
        serialized["totalChanges"] = total_changes
        result.append(serialized)
    return result


@router.get("/watches/{watch_id}", response_model=dict)
async def get_watch(watch_id: str, auth: AuthContext = Depends(get_current_user)):
    """Get a single watch — returns frontend Watch shape."""
    from app.db import get_supabase
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    # Tenant isolation check
    if str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")

    db = get_supabase()
    runs_r = await asyncio.to_thread(
        lambda: db.table("watch_runs").select("id", count="exact").eq("watch_id", watch_id).execute()
    )
    total_runs = runs_r.count if runs_r.count is not None else len(runs_r.data or [])
    changes_r = await asyncio.to_thread(
        lambda: db.table("changes").select("id", count="exact").eq("watch_id", watch_id).execute()
    )
    total_changes = changes_r.count if changes_r.count is not None else len(changes_r.data or [])

    serialized = serialize_watch(watch)
    serialized["totalRuns"] = total_runs
    serialized["totalChanges"] = total_changes
    return serialized


@router.patch("/watches/{watch_id}")
async def update_watch(watch_id: str, body: dict, auth: AuthContext = Depends(get_current_user)):
    """Partial update of a watch (name, description, schedule, integrations)."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    if str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    allowed = {"name", "description", "schedule", "integrations"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    updated = await svc.update_watch(watch_id, **updates)
    return serialize_watch(updated) if updated else serialize_watch(watch)


@router.delete("/watches/{watch_id}")
async def delete_watch(watch_id: str, auth: AuthContext = Depends(get_current_user)):
    """Delete a watch."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    if str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    await svc.delete_watch(watch_id)
    return {"status": "deleted"}


@router.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, auth: AuthContext = Depends(get_current_user)):
    """Trigger immediate watch execution. Returns run_id for polling."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    if str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    run = await svc.create_run(watch_id, organization_id=auth.organization_id, status="running")
    run_id = str(run["id"])
    enqueue_job("watch_run", {"watch_id": watch_id, "run_id": run_id})
    return {"status": "queued", "watch_id": watch_id, "run_id": run_id}


@router.post("/run-all")
async def run_all_watches(auth: AuthContext = Depends(get_current_user)):
    """Enqueue execution of all active watches for this org. Returns immediately."""
    enqueue_job("run_all", {"organization_id": auth.organization_id})
    return {"status": "queued", "message": "All active watches will be executed by the worker."}


@router.get("/watches/{watch_id}/history", response_model=dict)
async def get_watch_history(watch_id: str, limit: int = 50, offset: int = 0, auth: AuthContext = Depends(get_current_user)):
    """Get watch execution history."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    if str(watch.get("organization_id")) != auth.organization_id:
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
            agent_summary=r.get("agent_summary"),
            agent_thoughts=r.get("agent_thoughts"),
        ).model_dump() for r in runs],
        "total": len(runs),
    }


@router.get("/watches/{watch_id}/runs", response_model=dict)
async def get_watch_runs(watch_id: str, limit: int = 50, auth: AuthContext = Depends(get_current_user)):
    """Get runs for a watch — returns lean frontend Run[] shape."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    if str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")
    runs = await svc.get_watch_runs(watch_id, limit=limit)
    return {"runs": [serialize_run_lean(r, watch or {}) for r in runs]}


@router.get("/watches/{watch_id}/changes", response_model=dict)
async def get_watch_changes(watch_id: str, limit: int = 50, auth: AuthContext = Depends(get_current_user)):
    """Get changes for a specific watch — returns ChangeEvent[] shape."""
    from app.db import get_supabase
    # Verify ownership
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch or str(watch.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Watch not found")

    db = get_supabase()
    r = await asyncio.to_thread(
        lambda: (
            db.table("changes")
            .select("*, watches(name, jurisdiction, scope), evidence_bundles(linear_ticket_url)")
            .eq("watch_id", watch_id)
            .order("detected_at", desc=True)
            .limit(limit)
            .execute()
        )
    )
    result = []
    for row in (r.data or []):
        watch_data = row.pop("watches", None) or {}
        result.append(serialize_change_event(row, watch_data))
    return {"changes": result}


# ── Runs ────────────────────────────────────────────────────────────────────

@router.get("/runs/recent")
async def recent_runs(limit: int = 50, auth: AuthContext = Depends(get_current_user)):
    """Recent runs across all watches for this org — returns lean Run[] shape."""
    from app.db import get_supabase
    db = get_supabase()
    r = await asyncio.to_thread(
        lambda: (
            db.table("watch_runs")
            .select("*, watches(name, jurisdiction, scope)")
            .eq("organization_id", auth.organization_id)
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
    )
    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(serialize_run_lean(row, watch))
    return {"runs": result}


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(run_id: str, auth: AuthContext = Depends(get_current_user)):
    """Get a single run — returns full frontend Run shape with diff, artifacts, ticket."""
    from app.db import get_supabase
    svc = WatchService()
    run_row = await svc.get_run(run_id)
    if not run_row:
        raise HTTPException(status_code=404, detail="Run not found")
    # Tenant isolation via denormalized org_id
    if str(run_row.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")

    watch = await svc.get_watch(str(run_row["watch_id"])) if run_row.get("watch_id") else None
    db = get_supabase()

    changes_r = await asyncio.to_thread(
        lambda: db.table("changes").select("*").eq("run_id", run_id).order("detected_at").execute()
    )
    changes = changes_r.data or []

    evidence_r = await asyncio.to_thread(
        lambda: db.table("evidence_bundles").select("*").eq("run_id", run_id).order("created_at").execute()
    )
    evidence = evidence_r.data or []

    return serialize_run(run_row, watch, changes, evidence)


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str, auth: AuthContext = Depends(get_current_user)):
    """SSE stream for live run step updates."""
    svc = WatchService()
    # Verify access on first call
    run = await svc.get_run(run_id)
    if not run or str(run.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Run not found")

    async def events():
        while True:
            run = await svc.get_run(run_id)
            if not run:
                yield f"data: {json.dumps({'error': 'run not found'})}\n\n"
                break
            steps = run.get("run_steps_log") or []
            yield f"data: {json.dumps({'steps': steps, 'status': run['status']})}\n\n"
            if run["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(1.5)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Changes ─────────────────────────────────────────────────────────────────

@router.get("/changes", response_model=dict)
async def list_changes(limit: int = 50, watch_id: Optional[str] = None, auth: AuthContext = Depends(get_current_user)):
    """List changes across all watches for this org — returns ChangeEvent[] shape."""
    from app.db import get_supabase
    db = get_supabase()

    def _query():
        q = (
            db.table("changes")
            .select("*, watches(name, jurisdiction, scope), evidence_bundles(linear_ticket_url)")
            .eq("organization_id", auth.organization_id)
            .order("detected_at", desc=True)
            .limit(limit)
        )
        if watch_id:
            q = q.eq("watch_id", watch_id)
        return q.execute()

    r = await asyncio.to_thread(_query)
    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(serialize_change_event(row, watch))
    return {"changes": result}


# ── Globe ───────────────────────────────────────────────────────────────────

@router.get("/globe-points", response_model=dict)
async def globe_points(auth: AuthContext = Depends(get_current_user)):
    """Derive globe data from real watches — returns GlobePoint[]."""
    svc = WatchService()
    watches = await svc.list_watches(auth.organization_id)
    return {"points": serialize_globe_points(watches)}


# ── Evidence ─────────────────────────────────────────────────────────────────

@router.get("/evidence", response_model=dict)
async def list_evidence_bundles(limit: int = 50, offset: int = 0, auth: AuthContext = Depends(get_current_user)):
    """List all evidence bundles for this org (newest first)."""
    ev = EvidenceService()
    bundles = await ev.list_bundles(organization_id=auth.organization_id, limit=limit, offset=offset)
    return {"bundles": bundles, "total": len(bundles)}


@router.get("/evidence/{bundle_id}", response_model=dict)
async def get_evidence_bundle(bundle_id: str, auth: AuthContext = Depends(get_current_user)):
    """Get evidence bundle by ID."""
    ev = EvidenceService()
    bundle = await ev.get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    # Tenant isolation via denormalized org_id
    if str(bundle.get("organization_id")) != auth.organization_id:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    return bundle


# ── Auth info ───────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(auth: AuthContext = Depends(get_current_user)):
    """Return the current user's profile and org info."""
    from app.db import get_supabase
    db = get_supabase()
    org_r = await asyncio.to_thread(
        lambda: db.table("organizations").select("*").eq("id", auth.organization_id).single().execute()
    )
    org = org_r.data if org_r.data else {}
    return {
        "user": {
            "id": auth.user_id,
            "email": auth.email,
            "role": auth.role,
            "organizationId": auth.organization_id,
        },
        "organization": {
            "id": org.get("id"),
            "name": org.get("name"),
            "slug": org.get("slug"),
            "plan": org.get("plan", "free"),
        },
    }


# ── Health (public — no auth required) ──────────────────────────────────────

@router.get("/health")
async def health():
    """Health check with dependency status."""
    from app.config import get_config
    config = get_config()
    return {
        "status": "ok",
        "browser_use": bool(config.get("browser_use_api_key")),
        "anthropic": bool(config.get("anthropic_api_key")),
        "linear": bool(config.get("linear_api_key")),
    }
