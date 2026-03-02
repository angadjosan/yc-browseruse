"""Background worker process — dequeues jobs from Redis and executes them."""
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load .env before any app imports
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from app.queue import dequeue_job, enqueue_job, set_analysis_status, get_analysis_status
from app.services.orchestrator import OrchestratorEngine
from app.services.product_analyzer import ProductAnalyzer
from app.services.watch_service import WatchService
from app.serializers import serialize_watch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("worker")

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Job handlers ─────────────────────────────────────────────────────────────

async def handle_watch_run(payload: dict):
    """Execute a single watch run."""
    watch_id = payload["watch_id"]
    run_id = payload.get("run_id")
    logger.info(f"Executing watch_run: watch_id={watch_id} run_id={run_id}")
    orchestrator = OrchestratorEngine()
    await orchestrator.execute_watch(watch_id, run_id=run_id)
    logger.info(f"Completed watch_run: watch_id={watch_id}")


async def handle_analyze_product(payload: dict):
    """Run product analysis and write status updates to Redis."""
    job_id = payload["job_id"]
    product_url = payload["product_url"]
    organization_id = payload.get("organization_id")
    if not organization_id:
        logger.error(f"analyze_product job_id={job_id} missing organization_id")
        set_analysis_status(job_id, {"status": "failed", "error": "Missing organization_id"})
        return

    logger.info(f"Starting analyze_product: job_id={job_id} url={product_url} org={organization_id}")

    def _log(msg: str):
        status = get_analysis_status(job_id) or {}
        logs = status.get("logs", [])
        logs.append({"t": time.time(), "msg": msg})
        status["logs"] = logs
        status["status"] = "running"
        status["product_url"] = product_url
        set_analysis_status(job_id, status)

    # Initialize
    set_analysis_status(job_id, {
        "status": "running",
        "product_url": product_url,
        "organization_id": organization_id,
        "logs": [],
    })

    def _on_risks(risks: list):
        existing = get_analysis_status(job_id) or {}
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
        set_analysis_status(job_id, existing)

    try:
        analyzer = ProductAnalyzer(log_fn=_log, on_risks_found=_on_risks)
        result = await analyzer.analyze_product_url(
            product_url=product_url,
            organization_id=organization_id,
        )
        existing = get_analysis_status(job_id) or {}
        existing_logs = existing.get("logs", [])

        total_risks = len(result["risks"])
        watches_stored = result["watches"]
        watches_expected = total_risks
        watches_created = len(watches_stored)
        watches_failed = watches_expected - watches_created

        final_status: dict = {
            "status": "completed",
            "product_url": product_url,
            "organization_id": organization_id,
            "logs": existing_logs,
            "product_info": {
                "content_preview": result["product_info"]["content"][:500],
                "url": result["product_info"].get("url", product_url),
            },
            "risks_identified": total_risks,
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
            "watches_created": watches_created,
            "watches": [serialize_watch(w) for w in watches_stored],
        }

        if watches_failed > 0:
            final_status["watches_failed"] = watches_failed
            final_status["status"] = "completed_with_errors"
            logger.warning(
                "analyze_product job_id=%s: %d/%d watches failed to store",
                job_id, watches_failed, watches_expected,
            )
        else:
            logger.info(f"Completed analyze_product: job_id={job_id}")

        set_analysis_status(job_id, final_status)
    except Exception as e:
        logger.exception(f"analyze_product failed: job_id={job_id}")
        _log(f"Error: {str(e)}")
        existing = get_analysis_status(job_id) or {}
        existing_logs = existing.get("logs", [])
        set_analysis_status(job_id, {
            "status": "failed",
            "product_url": product_url,
            "logs": existing_logs,
            "error": str(e),
        })


async def handle_run_all(payload: dict):
    """Enqueue a watch_run job for every active watch in the given org."""
    organization_id = payload.get("organization_id")
    if not organization_id:
        logger.error("run_all job missing organization_id — listing all orgs")
        # Fallback: list all active watches across all orgs
        from app.db import get_supabase
        db = get_supabase()
        r = await asyncio.to_thread(
            lambda: db.table("watches").select("id, organization_id").eq("status", "active").execute()
        )
        watches = r.data or []
    else:
        logger.info(f"Handling run_all for org={organization_id}")
        svc = WatchService()
        watches = await svc.list_watches(organization_id)

    count = 0
    svc = WatchService()
    for w in watches:
        if w.get("status") != "active":
            continue
        org_id = str(w.get("organization_id", organization_id or ""))
        run = await svc.create_run(str(w["id"]), organization_id=org_id, status="running")
        enqueue_job("watch_run", {"watch_id": str(w["id"]), "run_id": str(run["id"])})
        count += 1
    logger.info(f"run_all: enqueued {count} watch_run jobs")


# ── Dispatcher ───────────────────────────────────────────────────────────────

DISPATCH = {
    "watch_run": handle_watch_run,
    "analyze_product": handle_analyze_product,
    "run_all": handle_run_all,
}


async def dispatch(job: dict):
    job_type = job["type"]
    handler = DISPATCH.get(job_type)
    if handler is None:
        logger.error(f"Unknown job type: {job_type}")
        return
    try:
        await handler(job["payload"])
    except Exception:
        logger.exception(f"Job {job['id']} (type={job_type}) failed")


# ── Scheduler ────────────────────────────────────────────────────────────────

def start_scheduler():
    """Start APScheduler to enqueue due watches every 15 minutes.

    Iterates ALL active watches across ALL organizations.
    """
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed — scheduled watch runs disabled")
        return None

    scheduler = AsyncIOScheduler()

    async def _tick():
        try:
            from app.db import get_supabase
            db = get_supabase()
            # Fetch all active watches across all orgs
            r = await asyncio.to_thread(
                lambda: db.table("watches").select("*").eq("status", "active").execute()
            )
            watches = r.data or []

            for w in watches:
                schedule = w.get("schedule") or {}
                cron_expr = schedule.get("cron")
                if not cron_expr:
                    continue
                last_run = w.get("last_run_at")
                if last_run:
                    try:
                        if isinstance(last_run, str):
                            last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                        else:
                            last_dt = last_run
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        if datetime.now(timezone.utc) - last_dt < timedelta(hours=1):
                            continue
                    except Exception:
                        pass
                org_id = str(w.get("organization_id", ""))
                svc = WatchService()
                logger.info(f"Scheduler: enqueuing watch {w['id']} ({w['name']}) org={org_id}")
                run = await svc.create_run(str(w["id"]), organization_id=org_id, status="running")
                enqueue_job("watch_run", {"watch_id": str(w["id"]), "run_id": str(run["id"])})
        except Exception:
            logger.exception("Scheduler tick failed")

    scheduler.add_job(_tick, CronTrigger(minute="*/15"), id="watch_scheduler", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (checking watches every 15 minutes)")
    return scheduler


# ── Main loop ────────────────────────────────────────────────────────────────

async def main():
    logger.info("Worker starting...")
    scheduler = start_scheduler()
    try:
        while not _shutdown:
            # dequeue_job is blocking (in a sync way), so run in thread
            job = await asyncio.to_thread(dequeue_job, 2)
            if job is None:
                continue
            logger.info(f"Dequeued job {job['id']} type={job['type']}")
            await dispatch(job)
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        logger.info("Worker shut down.")


if __name__ == "__main__":
    asyncio.run(main())
