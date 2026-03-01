"""FastAPI route definitions."""
import asyncio
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.schemas.watch import CreateWatchRequest, WatchRunSummary
from app.schemas.evidence import EvidenceBundleResponse
from app.services.watch_service import WatchService
from app.services.evidence_service import EvidenceService
from app.services.orchestrator import OrchestratorEngine
from app.services.product_analyzer import ProductAnalyzer

router = APIRouter(prefix="/api", tags=["api"])

# Default org for single-tenant; in production use auth
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# In-memory job store for product analysis (MVP: single-tenant, single process)
_analysis_jobs: Dict[str, Dict[str, Any]] = {}


class AnalyzeProductRequest(BaseModel):
    """Request to analyze a product URL and create compliance watches."""
    product_url: str


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
        "regulation_title": watch.get("regulation_title"),
        "risk_rationale": watch.get("risk_rationale"),
        "jurisdiction": watch.get("jurisdiction"),
        "scope": watch.get("scope"),
        "source_url": watch.get("source_url"),
        "check_interval_seconds": watch.get("check_interval_seconds"),
        "current_regulation_state": watch.get("current_regulation_state"),
    }


async def _run_analysis_background(job_id: str, product_url: str):
    """Background task: run product analysis and update job store."""
    _analysis_jobs[job_id]["status"] = "running"
    analyzer = ProductAnalyzer()
    try:
        result = await analyzer.analyze_product_url(
            product_url=product_url,
            organization_id=DEFAULT_ORG_ID,
        )
        _analysis_jobs[job_id].update({
            "status": "completed",
            "product_info": {
                "content_preview": result["product_info"]["content"][:500],
                "url": result["product_info"]["url"],
            },
            "risks_identified": len(result["risks"]),
            "watches_created": len(result["watches"]),
            "watches": [_watch_to_response(w) for w in result["watches"]],
        })
    except Exception as e:
        _analysis_jobs[job_id].update({"status": "failed", "error": str(e)})


@router.post("/analyze-product", response_model=dict)
async def analyze_product(request: AnalyzeProductRequest, background_tasks: BackgroundTasks):
    """Analyze a product URL and create compliance risk watches (runs in background).

    Returns immediately with a job_id. Poll GET /api/analyze-product/{job_id} for status.

    Workflow:
    1. Extract product information using browser-use agent
    2. Generate compliance risk analysis using Claude
    3. Create watches for each identified risk
    """
    job_id = str(uuid.uuid4())
    _analysis_jobs[job_id] = {"status": "pending", "product_url": request.product_url}
    background_tasks.add_task(_run_analysis_background, job_id, request.product_url)
    return {
        "status": "queued",
        "job_id": job_id,
        "product_url": request.product_url,
        "message": "Analysis started. Poll GET /api/analyze-product/{job_id} for status.",
    }


@router.get("/analyze-product/{job_id}", response_model=dict)
async def get_analysis_status(job_id: str):
    """Get the status of a product analysis job."""
    job = _analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"job_id": job_id, **job}


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
    """List all watches for the organization with run/change counts."""
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)

    # Batch: get all runs in one query per watch (but use aggregation columns)
    from app.db import get_supabase
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

        result.append(_watch_to_response(w, total_runs=total_runs, total_changes=total_changes))
    return result


@router.get("/watches/{watch_id}", response_model=dict)
async def get_watch(watch_id: str):
    """Get a single watch."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")

    from app.db import get_supabase
    db = get_supabase()
    runs_r = await asyncio.to_thread(
        lambda: db.table("watch_runs").select("id", count="exact").eq("watch_id", watch_id).execute()
    )
    total_runs = runs_r.count if runs_r.count is not None else len(runs_r.data or [])
    changes_r = await asyncio.to_thread(
        lambda: db.table("changes").select("id", count="exact").eq("watch_id", watch_id).execute()
    )
    total_changes = changes_r.count if changes_r.count is not None else len(changes_r.data or [])

    return _watch_to_response(watch, total_runs=total_runs, total_changes=total_changes)


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
            agent_summary=r.get("agent_summary"),
            agent_thoughts=r.get("agent_thoughts"),
        ).model_dump() for r in runs],
        "total": len(runs),
    }


@router.get("/runs/recent")
async def recent_runs(limit: int = 50):
    """Recent runs across all watches."""
    from app.db import get_supabase
    db = get_supabase()

    # Single query: join runs with watch names
    r = await asyncio.to_thread(
        lambda: (
            db.table("watch_runs")
            .select("*, watches(name)")
            .order("started_at", desc=True)
            .limit(limit)
            .execute()
        )
    )
    runs = []
    for row in (r.data or []):
        row["watch_name"] = row.pop("watches", {}).get("name") if isinstance(row.get("watches"), dict) else None
        runs.append(row)
    return {"runs": runs}


@router.get("/runs/{run_id}", response_model=dict)
async def get_run(run_id: str):
    """Get a single watch run by ID."""
    svc = WatchService()
    run = await svc.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    watch = await svc.get_watch(str(run["watch_id"])) if run.get("watch_id") else None
    return {
        "id": str(run["id"]),
        "watch_id": str(run["watch_id"]),
        "watch_name": watch.get("name") if watch else None,
        "status": run["status"],
        "started_at": run["started_at"],
        "completed_at": run.get("completed_at"),
        "duration_ms": run.get("duration_ms"),
        "tasks_executed": run.get("tasks_executed", 0),
        "tasks_failed": run.get("tasks_failed", 0),
        "changes_detected": run.get("changes_detected", 0),
        "error_message": run.get("error_message"),
        "agent_summary": run.get("agent_summary"),
        "agent_thoughts": run.get("agent_thoughts"),
    }


@router.get("/evidence", response_model=dict)
async def list_evidence_bundles(limit: int = 50, offset: int = 0):
    """List all evidence bundles (newest first)."""
    ev = EvidenceService()
    bundles = await ev.list_bundles(limit=limit, offset=offset)
    return {"bundles": bundles, "total": len(bundles)}


@router.get("/evidence/{bundle_id}", response_model=dict)
async def get_evidence_bundle(bundle_id: str):
    """Get evidence bundle by ID."""
    ev = EvidenceService()
    bundle = await ev.get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Evidence bundle not found")
    return bundle


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
        "slack": bool(config.get("slack_bot_token")),
    }
