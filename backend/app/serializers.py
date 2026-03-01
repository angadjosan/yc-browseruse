"""Serializers: map raw DB rows to frontend type shapes.

All camelCase output to match frontend types.ts exactly.
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


# ── Watch ──────────────────────────────────────────────────────────────────

CRON_TO_LABEL: Dict[str, str] = {
    "0 9 * * *": "daily",
    "0 9 * * 1": "weekly",
    "0 9 1 * *": "monthly",
    "0 * * * *": "hourly",
}

JURISDICTION_COORDS: Dict[str, Dict[str, float]] = {
    "EU":            {"lat": 50.85,  "lng": 4.35},
    "US":            {"lat": 38.9,   "lng": -77.0},
    "US-CA":         {"lat": 37.77,  "lng": -122.42},
    "California":    {"lat": 37.77,  "lng": -122.42},
    "UK":            {"lat": 51.51,  "lng": -0.09},
    "JP":            {"lat": 35.68,  "lng": 139.69},
    "AU":            {"lat": -33.86, "lng": 151.21},
    "CA":            {"lat": 45.42,  "lng": -75.69},
    "DE":            {"lat": 52.52,  "lng": 13.4},
    "FR":            {"lat": 48.85,  "lng": 2.35},
    "Global":        {"lat": 20.0,   "lng": 0.0},
    "United States": {"lat": 38.9,   "lng": -77.0},
    "Canada":        {"lat": 45.42,  "lng": -75.69},
    "Australia":     {"lat": -33.86, "lng": 151.21},
    "Japan":         {"lat": 35.68,  "lng": 139.69},
    "Germany":       {"lat": 52.52,  "lng": 13.4},
    "France":        {"lat": 48.85,  "lng": 2.35},
}


def serialize_watch(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a DB watches row → frontend Watch type."""
    config = row.get("config") or {}
    schedule_obj = row.get("schedule") or {}
    cron = schedule_obj.get("cron", "")
    schedule_label = CRON_TO_LABEL.get(cron, "daily")

    status = "healthy" if row.get("status") == "active" else "degraded"

    next_run_at = row.get("next_run_at")
    if not next_run_at and row.get("last_run_at"):
        next_run_at = _compute_next_run(row["last_run_at"], cron)

    # jurisdiction is a top-level DB column (string), not inside config
    jurisdiction = row.get("jurisdiction") or ""
    jurisdictions = [jurisdiction] if jurisdiction else []

    # source_url is a top-level DB column (string), not inside config
    source_url = row.get("source_url") or ""
    sources = [source_url] if source_url else []

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description") or "",
        "schedule": schedule_label,
        "jurisdictions": jurisdictions,
        "sources": sources,
        "status": status,
        "nextRunAt": next_run_at or "",
        "lastRunAt": row.get("last_run_at"),
        "riskRationale": row.get("risk_rationale") or "",
        "jurisdiction": jurisdiction,
        "scope": row.get("scope") or "",
        "sourceUrl": source_url,
        "checkIntervalSeconds": row.get("check_interval_seconds"),
        "currentRegulationState": row.get("current_regulation_state") or "",
        "type": row.get("type") or "custom",
    }


def _compute_next_run(last_run_at: str, cron: str) -> Optional[str]:
    try:
        last = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        deltas: Dict[str, timedelta] = {
            "0 9 * * *": timedelta(days=1),
            "0 9 * * 1": timedelta(weeks=1),
            "0 9 1 * *": timedelta(days=30),
            "0 * * * *": timedelta(hours=1),
        }
        delta = deltas.get(cron, timedelta(days=1))
        return (last + delta).isoformat()
    except Exception:
        return None


# ── ChangeEvent ────────────────────────────────────────────────────────────

IMPACT_TO_SEVERITY: Dict[str, str] = {
    "low": "low",
    "medium": "med",
    "high": "high",
}


def serialize_change_event(row: Dict[str, Any], watch: Dict[str, Any]) -> Dict[str, Any]:
    """Map a DB changes row + its watch row → frontend ChangeEvent type."""
    # jurisdiction is a top-level column on watches
    jurisdiction = (watch.get("jurisdiction") or "") if watch else ""

    # source_type: use scope field if it's a valid value, otherwise "regulator"
    scope = (watch.get("scope") or "") if watch else ""
    source_type = scope if scope in ("regulator", "vendor") else "regulator"

    return {
        "id": str(row["id"]),
        "watchId": str(row["watch_id"]),
        "title": watch.get("name", row.get("target_name", "")) if watch else row.get("target_name", ""),
        "memo": row.get("diff_summary") or "",
        "severity": IMPACT_TO_SEVERITY.get(row.get("impact_level", "medium"), "med"),
        "jurisdiction": jurisdiction,
        "sourceType": source_type,
        "createdAt": row.get("detected_at", ""),
        "runId": str(row["run_id"]),
    }


# ── Run ────────────────────────────────────────────────────────────────────

def serialize_run(
    run_row: Dict[str, Any],
    watch: Optional[Dict[str, Any]],
    changes: List[Dict[str, Any]],
    evidence_bundles: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Map a DB watch_runs row + related data → frontend Run type (full shape)."""
    # Prefer run_steps_log (real-time) over agent_thoughts (post-hoc)
    steps_log = run_row.get("run_steps_log") or []
    if steps_log:
        steps = steps_log
    else:
        steps = _agent_thoughts_to_steps(run_row.get("agent_thoughts") or [])

    # Always append Diffing + Ticketing steps once run is complete
    if run_row.get("status") in ("completed", "failed"):
        steps.append({
            "name": "Diffing",
            "status": "done",
            "timestamp": run_row.get("completed_at"),
        })
        steps.append({
            "name": "Ticketing",
            "status": "done",
            "timestamp": run_row.get("completed_at"),
        })

    return {
        "id": str(run_row["id"]),
        "watchId": str(run_row["watch_id"]),
        "watchName": watch.get("name") if watch else None,
        "startedAt": run_row["started_at"],
        "endedAt": run_row.get("completed_at") or run_row["started_at"],
        "steps": steps,
        "selfHealed": (
            (run_row.get("tasks_failed") or 0) > 0
            and run_row.get("status") == "completed"
        ),
        "retries": run_row.get("tasks_failed") or 0,
        "artifacts": _serialize_artifacts(evidence_bundles[0] if evidence_bundles else None),
        "diff": _serialize_diff(changes[0] if changes else None),
        "ticket": _serialize_ticket(evidence_bundles, changes),
        "impactMemo": _serialize_impact_memo(evidence_bundles[0] if evidence_bundles else None),
    }


def serialize_run_lean(
    run_row: Dict[str, Any],
    watch: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Lean Run shape for list views — skips expensive diff/artifacts/ticket joins."""
    steps_log = run_row.get("run_steps_log") or []
    steps = steps_log if steps_log else _agent_thoughts_to_steps(run_row.get("agent_thoughts") or [])

    return {
        "id": str(run_row["id"]),
        "watchId": str(run_row["watch_id"]),
        "watchName": watch.get("name") if watch else None,
        "startedAt": run_row["started_at"],
        "endedAt": run_row.get("completed_at") or run_row["started_at"],
        "steps": steps,
        "selfHealed": (
            (run_row.get("tasks_failed") or 0) > 0
            and run_row.get("status") == "completed"
        ),
        "retries": run_row.get("tasks_failed") or 0,
        "artifacts": [],
        "diff": {"before": "", "after": "", "highlights": []},
        "ticket": {"provider": "linear", "url": "", "title": ""},
    }


def _agent_thoughts_to_steps(thoughts: List[Any]) -> List[Dict[str, Any]]:
    """Convert BrowserUse AgentBrain objects → RunStep[]."""
    step_names = ["Searching", "Navigating", "Capturing", "Hashing"]
    if not thoughts:
        return [{"name": n, "status": "done"} for n in step_names]
    out = []
    for i, t in enumerate(thoughts[:4]):
        if isinstance(t, dict):
            name = (
                (t.get("current_state") or {}).get("next_goal")
                or t.get("thought")
                or t.get("text")
                or step_names[min(i, len(step_names) - 1)]
            )
        else:
            name = step_names[min(i, len(step_names) - 1)]
        out.append({
            "name": str(name)[:40],
            "status": "done",
            "timestamp": t.get("timestamp") if isinstance(t, dict) else None,
        })
    return out


def _serialize_diff(change: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not change:
        return {"before": "", "after": "", "highlights": []}
    details = change.get("diff_details") or {}
    text_diff = details.get("text_diff") or {}
    semantic = details.get("semantic_diff") or {}

    additions = text_diff.get("additions") or []
    deletions = text_diff.get("deletions") or []

    before = " ".join(deletions[:3]) if deletions else semantic.get("summary", "")
    after = " ".join(additions[:3]) if additions else semantic.get("summary", "")

    highlights = (
        [{"type": "remove", "text": d} for d in deletions[:5]]
        + [{"type": "add", "text": a} for a in additions[:5]]
    )
    compliance_summary = details.get("compliance_summary") or semantic.get("compliance_summary") or ""
    change_summary = details.get("change_summary") or semantic.get("change_summary") or change.get("diff_summary") or ""

    return {
        "before": before,
        "after": after,
        "highlights": highlights,
        "complianceSummary": compliance_summary,
        "changeSummary": change_summary,
    }


def _serialize_ticket(
    evidence_bundles: List[Dict[str, Any]],
    changes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    for eb in evidence_bundles:
        url = eb.get("linear_ticket_url") or eb.get("jira_ticket_url")
        if url:
            return {
                "provider": "jira" if "jira" in url else "linear",
                "url": url,
                "title": eb.get("ticket_title") or "Compliance change detected",
            }
    for c in changes:
        url = c.get("linear_ticket_url") or c.get("jira_ticket_url")
        if url:
            return {
                "provider": "jira" if "jira" in url else "linear",
                "url": url,
                "title": c.get("diff_summary") or "Compliance change detected",
            }
    return {"provider": "linear", "url": "", "title": "No ticket created"}


def _serialize_artifacts(bundle: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not bundle:
        return []
    artifacts = []
    for i, url in enumerate(bundle.get("screenshots") or []):
        artifacts.append({
            "id": f"{bundle['id']}-screenshot-{i}",
            "type": "screenshot",
            "label": "Before" if i == 0 else "After",
            "url": url,
            "timestamp": bundle.get("created_at", ""),
        })
    if bundle.get("content_hash_current"):
        artifacts.append({
            "id": f"{bundle['id']}-hash",
            "type": "hash",
            "label": "Content hash",
            "hash": f"sha256:{bundle['content_hash_current'][:16]}...",
            "timestamp": bundle.get("created_at", ""),
        })
    if bundle.get("diff_url"):
        artifacts.append({
            "id": f"{bundle['id']}-snapshot",
            "type": "snapshot",
            "label": "Diff snapshot",
            "url": bundle["diff_url"],
            "timestamp": bundle.get("created_at", ""),
        })
    return artifacts


def _serialize_impact_memo(bundle: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    if not bundle or not bundle.get("impact_memo"):
        return None
    memo = bundle["impact_memo"]
    parts = re.split(r"\n{2,}|(?=\d+\.\s)", memo.strip())
    return [p.strip() for p in parts if p.strip()][:6]


# ── GlobePoint ─────────────────────────────────────────────────────────────

def serialize_globe_points(watches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Derive GlobePoint[] from watches list — no extra DB query needed."""
    seen: set = set()
    points = []
    for w in watches:
        jurisdiction = w.get("jurisdiction") or ""
        scope = w.get("scope") or ""
        source_type = scope if scope in ("regulator", "vendor") else "regulator"

        key = f"{jurisdiction}:{w.get('name', '')}"
        if key not in seen and jurisdiction in JURISDICTION_COORDS:
            seen.add(key)
            points.append({
                "lat": JURISDICTION_COORDS[jurisdiction]["lat"],
                "lng": JURISDICTION_COORDS[jurisdiction]["lng"],
                "label": w.get("name", ""),
                "type": source_type,
                "jurisdiction": jurisdiction,
            })
    return points
