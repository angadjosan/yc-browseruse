"""Redis-backed job queue for background work."""
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None

QUEUE_KEY = "ccr:jobs"
ANALYSIS_KEY_PREFIX = "ccr:analysis:"


def get_redis() -> redis.Redis:
    """Return a singleton Redis connection."""
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", "redis://localhost:6379")
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def enqueue_job(job_type: str, payload: Dict[str, Any]) -> str:
    """Push a job onto the Redis queue. Returns the job ID."""
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "type": job_type,
        "payload": payload,
        "enqueued_at": time.time(),
    }
    get_redis().rpush(QUEUE_KEY, json.dumps(job))
    logger.info(f"Enqueued job {job_id} type={job_type}")
    return job_id


def dequeue_job(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Blocking pop from the job queue. Returns parsed job dict or None on timeout."""
    r = get_redis()
    result = r.blpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


# ── Analysis job status (stored in Redis hashes) ────────────────────────────

def set_analysis_status(job_id: str, data: Dict[str, Any]) -> None:
    """Write analysis job status to Redis hash."""
    r = get_redis()
    r.set(f"{ANALYSIS_KEY_PREFIX}{job_id}", json.dumps(data, default=str))
    # Expire after 24 hours so we don't leak memory
    r.expire(f"{ANALYSIS_KEY_PREFIX}{job_id}", 86400)


def get_analysis_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Read analysis job status from Redis."""
    r = get_redis()
    raw = r.get(f"{ANALYSIS_KEY_PREFIX}{job_id}")
    if raw is None:
        return None
    return json.loads(raw)
