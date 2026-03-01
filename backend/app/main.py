"""Compliance Change Radar — FastAPI application."""
import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ or project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _start_scheduler():
    """Start APScheduler to run active watches on their cron schedules."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = AsyncIOScheduler()

    async def _tick():
        """Check for watches that need to run and execute them."""
        try:
            from app.services.watch_service import WatchService
            from app.services.orchestrator import OrchestratorEngine

            svc = WatchService()
            watches = await svc.list_watches("00000000-0000-0000-0000-000000000001")
            for w in watches:
                if w.get("status") != "active":
                    continue
                schedule = w.get("schedule") or {}
                cron_expr = schedule.get("cron")
                if not cron_expr:
                    continue
                # Check if the watch should run now by comparing next_run_at
                # For simplicity in the MVP, we let APScheduler handle the 1-minute tick
                # and check if enough time has passed since last_run_at
                last_run = w.get("last_run_at")
                if last_run:
                    from datetime import datetime, timedelta, timezone
                    try:
                        if isinstance(last_run, str):
                            last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                        else:
                            last_dt = last_run
                        if last_dt.tzinfo is None:
                            last_dt = last_dt.replace(tzinfo=timezone.utc)
                        # Don't re-run if ran within the last hour
                        if datetime.now(timezone.utc) - last_dt < timedelta(hours=1):
                            continue
                    except Exception:
                        pass

                logger.info(f"Scheduler: executing watch {w['id']} ({w['name']})")
                orchestrator = OrchestratorEngine()
                asyncio.create_task(orchestrator.execute_watch(str(w["id"])))
        except Exception:
            logger.exception("Scheduler tick failed")

    # Run every 15 minutes
    scheduler.add_job(_tick, CronTrigger(minute="*/15"), id="watch_scheduler", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (checking watches every 15 minutes)")
    return scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = _start_scheduler()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Compliance Change Radar API",
    description="Describe your product; we watch every regulation and vendor policy that affects you and ticket your team when something changes.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": "Compliance Change Radar API", "docs": "/docs"}
