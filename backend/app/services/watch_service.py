"""Watch CRUD and run scheduling."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.db import get_supabase
from app.schemas.watch import CreateWatchRequest, WatchResponse, WatchRunSummary


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
    ) -> Dict[str, Any]:
        """Create a new watch. Default schedule: daily."""
        schedule = config.get("schedule", {"cron": "0 9 * * *", "timezone": "UTC"}) if config else {"cron": "0 9 * * *", "timezone": "UTC"}
        if config is None:
            config = {}
        if "schedule" not in config:
            config = {**config, "schedule": schedule}
        row = {
            "organization_id": organization_id,
            "name": name,
            "description": description or "",
            "config": config,
            "schedule": schedule,
            "integrations": integrations or {},
            "status": "active",
        }
        r = self.db.table("watches").insert(row).execute()
        if not r.data:
            raise ValueError("Failed to create watch")
        return r.data[0]

    async def get_watch(self, watch_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.table("watches").select("*").eq("id", watch_id).execute()
        return r.data[0] if r.data else None

    async def list_watches(self, organization_id: str) -> List[Dict[str, Any]]:
        r = (
            self.db.table("watches")
            .select("*")
            .eq("organization_id", organization_id)
            .order("created_at", desc=True)
            .execute()
        )
        return r.data or []

    async def update_watch(self, watch_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        r = self.db.table("watches").update(kwargs).eq("id", watch_id).execute()
        return r.data[0] if r.data else None

    async def delete_watch(self, watch_id: str) -> bool:
        r = self.db.table("watches").delete().eq("id", watch_id).execute()
        return True

    async def get_watch_runs(self, watch_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        r = (
            self.db.table("watch_runs")
            .select("*")
            .eq("watch_id", watch_id)
            .order("started_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return r.data or []

    async def create_run(
        self,
        watch_id: str,
        status: str = "running",
    ) -> Dict[str, Any]:
        row = {"watch_id": watch_id, "status": status}
        r = self.db.table("watch_runs").insert(row).execute()
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
        if not payload:
            return await self.get_run(run_id)
        r = self.db.table("watch_runs").update(payload).eq("id", run_id).execute()
        return r.data[0] if r.data else None

    async def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        r = self.db.table("watch_runs").select("*").eq("id", run_id).execute()
        return r.data[0] if r.data else None

    async def save_snapshot(
        self,
        watch_id: str,
        run_id: str,
        target_name: str,
        url: str,
        content_text: str,
        content_hash: str,
        screenshot_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
        r = self.db.table("snapshots").insert(row).execute()
        if not r.data:
            raise ValueError("Failed to save snapshot")
        return r.data[0]

    async def get_previous_snapshot(self, watch_id: str, target_name: str) -> Optional[Dict[str, Any]]:
        """Latest snapshot for this watch+target from a previous run."""
        r = (
            self.db.table("snapshots")
            .select("*")
            .eq("watch_id", watch_id)
            .eq("target_name", target_name)
            .order("captured_at", desc=True)
            .limit(1)
            .execute()
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
