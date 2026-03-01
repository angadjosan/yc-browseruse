"""FastAPI route definitions."""
import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.schemas.watch import CreateWatchRequest, WatchRunSummary
from app.schemas.evidence import EvidenceBundleResponse
from app.services.watch_service import WatchService
from app.services.evidence_service import EvidenceService
from app.services.orchestrator import OrchestratorEngine
from app.services.product_analyzer import ProductAnalyzer
from app.serializers import (
    serialize_watch,
    serialize_change_event,
    serialize_run,
    serialize_run_lean,
    serialize_globe_points,
)

router = APIRouter(prefix="/api", tags=["api"])

# Default org for single-tenant; in production use auth
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# File-backed job store — survives server restarts during demo
_JOBS_FILE = Path(__file__).resolve().parent.parent.parent / ".analysis_jobs.json"


def _load_jobs() -> Dict[str, Any]:
    try:
        if _JOBS_FILE.exists():
            return json.loads(_JOBS_FILE.read_text())
    except Exception:
        pass
    return {}


def _save_job(job_id: str, data: Dict[str, Any]) -> None:
    try:
        jobs = _load_jobs()
        jobs[job_id] = data
        _JOBS_FILE.write_text(json.dumps(jobs, default=str))
    except Exception:
        pass


class _CallbackLogHandler(logging.Handler):
    """Forwards log records to a callback (e.g. to persist in job logs for the /analyze UI)."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if msg:
                self._callback(msg)
        except Exception:
            pass


class AnalyzeProductRequest(BaseModel):
    """Request to analyze a product URL and create compliance watches."""
    product_url: str


# ── Background helpers ──────────────────────────────────────────────────────

async def _execute_watch_background(watch_id: str, run_id: Optional[str] = None):
    orchestrator = OrchestratorEngine()
    await orchestrator.execute_watch(watch_id, run_id=run_id)


async def _run_analysis_background(job_id: str, product_url: str):
    """Background task: run product analysis and update job store."""

    def _log(msg: str):
        jobs = _load_jobs()
        job = jobs.get(job_id, {})
        # Append to logs, initializing if needed
        if "logs" not in job:
            job["logs"] = []
        job["logs"].append({"t": time.time(), "msg": msg})
        job["status"] = "running"
        job["product_url"] = product_url
        _save_job(job_id, job)

    # Initialize job as running and empty logs
    _save_job(job_id, {"status": "running", "product_url": product_url, "logs": []})

    def _on_risks(risks: list):
        """Push risks into the job store immediately so the frontend can display them."""
        existing = _load_jobs().get(job_id, {})
        existing["risks_identified"] = len(risks)
        existing["risks"] = [
            {
                "regulation_title": r.get("regulation_title", ""),
                "risk_rationale": r.get("risk_rationale", ""),
                "jurisdiction": r.get("jurisdiction", ""),
                "scope": r.get("scope", ""),
                "source_url": r.get("source_url", ""),
                "check_interval_seconds": r.get("check_interval_seconds", 86400),
            }
            for r in risks
        ]
        _save_job(job_id, existing)

    # Capture browser_use library logs (agent steps, navigate, click, etc.) into job logs
    # so they show up on the /analyze route when the frontend polls.
    bu_logger = logging.getLogger("browser_use")
    prev_level = bu_logger.level
    bu_logger.setLevel(logging.INFO)
    handler = _CallbackLogHandler(_log)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    bu_logger.addHandler(handler)
    try:
        await _run_analysis_with_handler(job_id, product_url, _log, _on_risks)
    finally:
        bu_logger.removeHandler(handler)
        bu_logger.setLevel(prev_level)


async def _run_analysis_with_handler(
    job_id: str, product_url: str, _log: Callable[[str], None], _on_risks: Callable[[list], None]
):
    """Run product analysis (called with browser_use log handler already attached)."""
    analyzer = ProductAnalyzer(log_fn=_log, on_risks_found=_on_risks)
    try:
        result = await analyzer.analyze_product_url(
            product_url=product_url,
            organization_id=DEFAULT_ORG_ID,
        )
        # Preserve accumulated logs when writing final state
        existing = _load_jobs().get(job_id, {})
        existing_logs = existing.get("logs", [])
        _save_job(job_id, {
            "status": "completed",
            "product_url": product_url,
            "logs": existing_logs,
            "product_info": {
                "content_preview": result["product_info"]["content"][:500],
                "url": result["product_info"].get("url", product_url),
            },
            "risks_identified": len(result["risks"]),
            "risks": [
                {
                    "regulation_title": r.get("regulation_title", ""),
                    "risk_rationale": r.get("risk_rationale", ""),
                    "jurisdiction": r.get("jurisdiction", ""),
                    "scope": r.get("scope", ""),
                    "source_url": r.get("source_url", ""),
                    "check_interval_seconds": r.get("check_interval_seconds", 86400),
                }
                for r in result["risks"]
            ],
            "watches_created": len(result["watches"]),
            "watches": [serialize_watch(w) for w in result["watches"]],
        })
    except Exception as e:
        _log(f"Error: {str(e)}")
        existing = _load_jobs().get(job_id, {})
        existing_logs = existing.get("logs", [])
        _save_job(job_id, {
            "status": "failed",
            "product_url": product_url,
            "logs": existing_logs,
            "error": str(e),
        })


# ── Product analysis (onboarding) ───────────────────────────────────────────

@router.post("/analyze-product", response_model=dict)
async def analyze_product(request: AnalyzeProductRequest, background_tasks: BackgroundTasks):
    """Analyze a product URL and create compliance risk watches (runs in background).

    Returns immediately with a job_id. Poll GET /api/analyze-product/{job_id} for status.
    """
    job_id = str(uuid.uuid4())
    _save_job(job_id, {"status": "pending", "product_url": request.product_url})
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
    job = _load_jobs().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis job not found")
    return {"job_id": job_id, **job}


# ── Watches ─────────────────────────────────────────────────────────────────

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
    return serialize_watch(watch)


@router.get("/watches", response_model=List[dict])
async def list_watches():
    """List all watches for the organization — returns frontend Watch[] shape."""
    from app.db import get_supabase
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
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
        # Attach counts as extra fields (frontend ignores unknown keys)
        serialized["totalRuns"] = total_runs
        serialized["totalChanges"] = total_changes
        result.append(serialized)
    return result


@router.get("/watches/{watch_id}", response_model=dict)
async def get_watch(watch_id: str):
    """Get a single watch — returns frontend Watch shape."""
    from app.db import get_supabase
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
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


@router.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, background_tasks: BackgroundTasks):
    """Trigger immediate watch execution. Returns run_id for polling."""
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(status_code=404, detail="Watch not found")
    # Create the run row NOW so we have a run_id to return immediately
    run = await svc.create_run(watch_id, status="running")
    run_id = str(run["id"])
    background_tasks.add_task(_execute_watch_background, watch_id, run_id)
    return {"status": "queued", "watch_id": watch_id, "run_id": run_id}


@router.get("/watches/{watch_id}/history", response_model=dict)
async def get_watch_history(watch_id: str, limit: int = 50, offset: int = 0):
    """Get watch execution history (raw shape, for backward compat)."""
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


@router.get("/watches/{watch_id}/runs", response_model=dict)
async def get_watch_runs(watch_id: str, limit: int = 50):
    """Get runs for a watch — returns lean frontend Run[] shape."""
    svc = WatchService()
    runs = await svc.get_watch_runs(watch_id, limit=limit)
    watch = await svc.get_watch(watch_id)
    return {"runs": [serialize_run_lean(r, watch or {}) for r in runs]}


@router.get("/watches/{watch_id}/changes", response_model=dict)
async def get_watch_changes(watch_id: str, limit: int = 50):
    """Get changes for a specific watch — returns ChangeEvent[] shape."""
    from app.db import get_supabase
    db = get_supabase()
    r = await asyncio.to_thread(
        lambda: (
            db.table("changes")
            .select("*, watches(name, jurisdiction, scope)")
            .eq("watch_id", watch_id)
            .order("detected_at", desc=True)
            .limit(limit)
            .execute()
        )
    )
    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(serialize_change_event(row, watch))
    return {"changes": result}


# ── Runs ────────────────────────────────────────────────────────────────────

@router.get("/runs/recent")
async def recent_runs(limit: int = 50):
    """Recent runs across all watches — returns lean Run[] shape."""
    from app.db import get_supabase
    db = get_supabase()
    r = await asyncio.to_thread(
        lambda: (
            db.table("watch_runs")
            .select("*, watches(name, jurisdiction, scope)")
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
async def get_run(run_id: str):
    """Get a single run — returns full frontend Run shape with diff, artifacts, ticket."""
    from app.db import get_supabase
    svc = WatchService()
    run_row = await svc.get_run(run_id)
    if not run_row:
        raise HTTPException(status_code=404, detail="Run not found")

    watch = await svc.get_watch(str(run_row["watch_id"])) if run_row.get("watch_id") else None
    db = get_supabase()

    changes_r = await asyncio.to_thread(
        lambda: db.table("changes").select("*").eq("run_id", run_id).order("created_at").execute()
    )
    changes = changes_r.data or []

    evidence_r = await asyncio.to_thread(
        lambda: db.table("evidence_bundles").select("*").eq("run_id", run_id).order("created_at").execute()
    )
    evidence = evidence_r.data or []

    return serialize_run(run_row, watch, changes, evidence)


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str):
    """SSE stream for live run step updates."""
    svc = WatchService()

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
async def list_changes(limit: int = 50, watch_id: Optional[str] = None):
    """List changes across all watches — returns ChangeEvent[] shape."""
    from app.db import get_supabase
    db = get_supabase()

    def _query():
        q = (
            db.table("changes")
            .select("*, watches(name, jurisdiction, scope)")
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
async def globe_points():
    """Derive globe data from real watches — returns GlobePoint[]."""
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    return {"points": serialize_globe_points(watches)}


# ── Evidence ─────────────────────────────────────────────────────────────────

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


# ── Health ───────────────────────────────────────────────────────────────────

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
