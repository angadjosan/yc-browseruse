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

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
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
    logger.info(f"Starting analyze_product: job_id={job_id} url={product_url}")

    def _log(msg: str):
        status = get_analysis_status(job_id) or {}
        logs = status.get("logs", [])
        logs.append({"t": time.time(), "msg": msg})
        status["logs"] = logs
        status["status"] = "running"
        status["product_url"] = product_url
        set_analysis_status(job_id, status)

    # Initialize
    set_analysis_status(job_id, {"status": "running", "product_url": product_url, "logs": []})

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
            organization_id=DEFAULT_ORG_ID,
        )
        existing = get_analysis_status(job_id) or {}
        existing_logs = existing.get("logs", [])
        set_analysis_status(job_id, {
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
        logger.info(f"Completed analyze_product: job_id={job_id}")
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
    """Enqueue a watch_run job for every active watch."""
    logger.info("Handling run_all: loading active watches")
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    count = 0
    for w in watches:
        if w.get("status") != "active":
            continue
        run = await svc.create_run(str(w["id"]), status="running")
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
    """Start APScheduler to enqueue due watches every 15 minutes."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed — scheduled watch runs disabled")
        return None

    scheduler = AsyncIOScheduler()

    async def _tick():
        try:
            svc = WatchService()
            watches = await svc.list_watches(DEFAULT_ORG_ID)
            for w in watches:
                if w.get("status") != "active":
                    continue
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
                logger.info(f"Scheduler: enqueuing watch {w['id']} ({w['name']})")
                run = await svc.create_run(str(w["id"]), status="running")
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
