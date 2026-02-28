from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EvidenceBundleResponse(BaseModel):
    id: str
    run_id: Optional[str] = None
    change_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    impact_memo: Optional[str] = None
    diff_summary: Optional[str] = None
    screenshots: List[Dict[str, Any]] = []
    content_hash: Optional[str] = None
    audit_metadata: Optional[Dict[str, Any]] = None
    s3_urls: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True
