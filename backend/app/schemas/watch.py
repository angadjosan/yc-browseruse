from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CreateWatchRequest(BaseModel):
    name: str
    description: Optional[str] = None
    type: str = "custom"  # regulation, vendor, internal, custom
    config: Dict[str, Any] = Field(default_factory=dict)
    integrations: Optional[Dict[str, Any]] = None


class WatchResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    next_run_at: Optional[datetime] = None
    total_runs: int = 0
    total_changes: int = 0
    config: Optional[Dict[str, Any]] = None
    schedule: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WatchRunSummary(BaseModel):
    id: str
    watch_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    tasks_executed: int = 0
    tasks_failed: int = 0
    changes_detected: int = 0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class WatchRunResponse(BaseModel):
    watch_id: str
    runs: List[WatchRunSummary]
    total: int


class RunWatchResponse(BaseModel):
    status: str = "queued"
    watch_id: str
    message: str = "Watch execution started"
