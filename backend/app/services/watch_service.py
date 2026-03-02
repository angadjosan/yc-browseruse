"""Watch CRUD and run scheduling."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from postgrest.exceptions import APIError

from app.db import get_supabase
from app.schemas.watch import CreateWatchRequest, WatchResponse, WatchRunSummary

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 0.5  # seconds; exponential backoff: 0.5, 1.0, 2.0


class WatchService:
    def __init__(self):
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_supabase()
        return self._db

    async def create_watch(
        self,
        organization_id: str,
        name: str,
        description: Optional[str] = None,
        watch_type: str = "custom",
        config: Optional[Dict[str, Any]] = None,
        integrations: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None,
        regulation_title: Optional[str] = None,
        risk_rationale: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        scope: Optional[str] = None,
        source_url: Optional[str] = None,
        check_interval_seconds: Optional[int] = None,
        current_regulation_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new watch with retry logic for transient failures."""
        schedule = config.get("schedule", {"cron": "0 9 * * *", "timezone": "UTC"}) if config else {"cron": "0 9 * * *", "timezone": "UTC"}
        if config is None:
            config = {}
        if "schedule" not in config:
            config = {**config, "schedule": schedule}
        row = {
            "organization_id": organization_id,
            "name": name,
            "description": description or "",
            "type": watch_type,
            "config": config,
            "schedule": schedule,
            "integrations": integrations or {},
            "status": "active",
        }

        if created_by is not None:
            row["created_by"] = created_by
        if regulation_title is not None:
            row["regulation_title"] = regulation_title
        if risk_rationale is not None:
            row["risk_rationale"] = risk_rationale
        if jurisdiction is not None:
            row["jurisdiction"] = jurisdiction
        if scope is not None:
            row["scope"] = scope
        if source_url is not None:
            row["source_url"] = source_url
        if check_interval_seconds is not None:
            row["check_interval_seconds"] = check_interval_seconds
        if current_regulation_state is not None:
            row["current_regulation_state"] = current_regulation_state

        last_err: Optional[Exception] = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = await asyncio.to_thread(
                    lambda: self.db.table("watches").insert(row).execute()
                )
                if not r.data:
                    raise ValueError("Supabase insert returned empty data")
                return r.data[0]
            except Exception as e:
                last_err = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "create_watch attempt %d/%d failed for '%s': %s — retrying in %.1fs",
                        attempt, MAX_RETRIES, name, e, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "create_watch failed after %d attempts for '%s': %s",
                        MAX_RETRIES, name, e,
                    )
        raise last_err  # type: ignore[misc]

    async def get_watch(self, watch_id: str) -> Optional[Dict[str, Any]]:
        r = await asyncio.to_thread(
            lambda: self.db.table("watches").select("*").eq("id", watch_id).execute()
        )
        return r.data[0] if r.data else None

    async def list_watches(self, organization_id: str) -> List[Dict[str, Any]]:
        r = await asyncio.to_thread(
            lambda: (
                self.db.table("watches")
                .select("*")
                .eq("organization_id", organization_id)
                .order("created_at", desc=True)
                .execute()
            )
        )
        return r.data or []

    async def update_watch(self, watch_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        r = await asyncio.to_thread(
            lambda: self.db.table("watches").update(kwargs).eq("id", watch_id).execute()
        )
        return r.data[0] if r.data else None

    async def delete_watch(self, watch_id: str) -> bool:
        await asyncio.to_thread(
            lambda: self.db.table("watches").delete().eq("id", watch_id).execute()
        )
        return True

    async def get_watch_runs(self, watch_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        r = await asyncio.to_thread(
            lambda: (
                self.db.table("watch_runs")
                .select("*")
                .eq("watch_id", watch_id)
                .order("started_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
        )
        return r.data or []

    async def create_run(
        self,
        watch_id: str,
        organization_id: Optional[str] = None,
        status: str = "running",
    ) -> Dict[str, Any]:
        # If org_id not provided, look it up from the watch
        if not organization_id:
            watch = await self.get_watch(watch_id)
            organization_id = str(watch["organization_id"]) if watch else None
        row = {"watch_id": watch_id, "status": status}
        if organization_id:
            row["organization_id"] = organization_id
        r = await asyncio.to_thread(
            lambda: self.db.table("watch_runs").insert(row).execute()
        )
        if not r.data:
            raise ValueError("Failed to create run")
        return r.data[0]

    async def update_run(
        self,
        run_id: str,
        status: Optional[str] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        tasks_executed: Optional[int] = None,
        tasks_failed: Optional[int] = None,
        changes_detected: Optional[int] = None,
        error_message: Optional[str] = None,
        agent_summary: Optional[str] = None,
        agent_thoughts: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        payload = {}
        if status is not None:
            payload["status"] = status
        if completed_at is not None:
            payload["completed_at"] = completed_at.isoformat()
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if tasks_executed is not None:
            payload["tasks_executed"] = tasks_executed
        if tasks_failed is not None:
            payload["tasks_failed"] = tasks_failed
        if changes_detected is not None:
            payload["changes_detected"] = changes_detected
        if error_message is not None:
            payload["error_message"] = error_message
        if agent_summary is not None:
            payload["agent_summary"] = agent_summary
        if agent_thoughts is not None:
            payload["agent_thoughts"] = agent_thoughts
        if not payload:
            return await self.get_run(run_id)
        try:
            r = await asyncio.to_thread(
                lambda: self.db.table("watch_runs").update(payload).eq("id", run_id).execute()
            )
            return r.data[0] if r.data else None
        except APIError as e:
            if e.code == "PGRST204" and ("agent_summary" in str(e) or "agent_thoughts" in str(e)):
                for key in ("agent_summary", "agent_thoughts"):
                    payload.pop(key, None)
                if payload:
                    r = await asyncio.to_thread(
                        lambda: self.db.table("watch_runs").update(payload).eq("id", run_id).execute()
                    )
                    return r.data[0] if r.data else None
            raise

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        r = await asyncio.to_thread(
            lambda: self.db.table("watch_runs").select("*").eq("id", run_id).execute()
        )
        return r.data[0] if r.data else None

    async def save_snapshot(
        self,
        watch_id: str,
        run_id: str,
        target_name: str,
        url: str,
        content_text: str,
        content_hash: str,
        organization_id: Optional[str] = None,
        screenshot_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        # If org_id not provided, look it up from the watch
        if not organization_id:
            watch = await self.get_watch(watch_id)
            organization_id = str(watch["organization_id"]) if watch else None
        row = {
            "watch_id": watch_id,
            "run_id": run_id,
            "target_name": target_name,
            "url": url,
            "content_text": content_text,
            "content_hash": content_hash,
            "screenshot_url": screenshot_url,
            "metadata": metadata or {},
        }
        if organization_id:
            row["organization_id"] = organization_id
        r = await asyncio.to_thread(
            lambda: self.db.table("snapshots").insert(row).execute()
        )
        if not r.data:
            raise ValueError("Failed to save snapshot")
        return r.data[0]

    async def get_previous_snapshot(self, watch_id: str, target_name: str) -> Optional[Dict[str, Any]]:
        """Latest snapshot for this watch+target from a previous run."""
        r = await asyncio.to_thread(
            lambda: (
                self.db.table("snapshots")
                .select("*")
                .eq("watch_id", watch_id)
                .eq("target_name", target_name)
                .order("captured_at", desc=True)
                .limit(1)
                .execute()
            )
        )
        return r.data[0] if r.data else None

    async def update_regulation_state(self, watch_id: str, new_state: str) -> Optional[Dict[str, Any]]:
        """Update the current regulation state for a watch."""
        r = await asyncio.to_thread(
            lambda: self.db.table("watches").update({"current_regulation_state": new_state}).eq("id", watch_id).execute()
        )
        return r.data[0] if r.data else None

    def to_watch_response(self, row: Dict[str, Any], total_runs: int = 0, total_changes: int = 0) -> Dict[str, Any]:
        return {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row.get("description"),
            "status": row.get("status", "active"),
            "next_run_at": row.get("next_run_at"),
            "total_runs": total_runs,
            "total_changes": total_changes,
            "config": row.get("config"),
            "schedule": row.get("schedule"),
            "created_at": row.get("created_at"),
            "last_run_at": row.get("last_run_at"),
        }
