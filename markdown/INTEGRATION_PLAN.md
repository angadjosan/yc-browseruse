# Full-Stack Integration Plan
## Frontend ↔ Backend ↔ AI Pipeline

> **Core philosophy: the frontend's `types.ts` is the API contract. The backend serializes its DB rows into those exact shapes. The frontend barely changes — it just swaps `import { ... } from "@/lib/mockData"` for `useSWR` calls. No adapter layer. No shape translation on the frontend. The backend does all the work.**

---

## Table of Contents

1. [Current State Audit](#1-current-state-audit)
2. [The Frontend Type Contract](#2-the-frontend-type-contract)
3. [Backend Serialization Rules](#3-backend-serialization-rules)
4. [New Backend Endpoints to Add](#4-new-backend-endpoints-to-add)
5. [New Database Columns to Add](#5-new-database-columns-to-add)
6. [Frontend Changes (Minimal)](#6-frontend-changes-minimal)
7. [Page-by-Page Wiring](#7-page-by-page-wiring)
8. [Real-Time Run Progress](#8-real-time-run-progress)
9. [AI Onboarding Flow](#9-ai-onboarding-flow)
10. [Implementation Order](#10-implementation-order)

---

## 1. Current State Audit

### Frontend (branch: `main`)

Every page reads from `src/lib/mockData.ts`. Nothing hits the network. The frontend has beautiful, well-structured types in `src/lib/types.ts` — those types become the law.

A legacy `src/lib/api.ts` already exists but uses **raw snake_case DB shapes** (`next_run_at`, `watch_id`, etc.) that don't match `types.ts`. It must be **replaced** entirely with the new typed API client described in §6a.

| Page | Mock source used | Real endpoint needed |
|------|----------------|---------------------|
| `/app` (Dashboard) | `changeEvents`, `globePoints` (WatchesCard imports internally) | `GET /api/watches`, `GET /api/changes`, `GET /api/globe-points` |
| `/watches` | `watches` | `GET /api/watches` |
| `/watches/[id]` | `watches`, `runs` | `GET /api/watches/{id}`, `GET /api/watches/{id}/runs` |
| `/app/run/[id]` | `runs` via `getRunById` | `GET /api/runs/{id}` (full shape) |
| `/history` | `runs` | `GET /api/runs/recent` |

**Important component notes:**
- `WatchesCard` internally calls `getWatchesByJurisdiction()` from mockData — it has **no `watches` prop**. Wiring requires adding a `watches` prop to `WatchesCard` (see §7).
- `ChangesCard` accepts `changes: ChangeEvent[]` as a prop, driven by dashboard state.
- The `CommandBar` "Run All" button drives a fake step animation — no API call.

### Backend (branch: `main`)

Fully wired FastAPI + Supabase pipeline. Existing endpoints:

```
POST   /api/watches                  create watch
GET    /api/watches                  list watches
GET    /api/watches/{id}             single watch
POST   /api/watches/{id}/run         trigger run (backgrounded)
GET    /api/watches/{id}/history     runs for a watch (raw shape)
GET    /api/runs/recent              all recent runs (raw shape)
GET    /api/runs/{id}                single run (raw shape)
GET    /api/evidence                 list evidence bundles
GET    /api/evidence/{id}            single evidence bundle
GET    /api/health                   dependency status
POST   /api/analyze-product          queue product analysis (returns job_id)
GET    /api/analyze-product/{job_id} poll analysis job status
```

**AI pipeline writes per run:**
- `watch_runs.agent_summary` — Claude-written one-liner
- `watch_runs.agent_thoughts` — BrowserUse `AgentBrain` objects (step reasoning)
- `snapshots` — raw scraped text + hash + URL per target
- `changes.diff_details` — `{text_diff: {additions, deletions}, semantic_diff: {summary, impact_level, key_changes, recommended_actions}}`
- `evidence_bundles` — Claude impact memo, screenshots, content hashes, HMAC signature

**DB watch column layout (important for serializers):**
- `jurisdiction` — top-level string column (e.g. `"EU"`, `"California"`) set by `ProductAnalyzer`
- `source_url` — top-level string column (URL to regulation source)
- `regulation_title`, `risk_rationale`, `scope`, `check_interval_seconds`, `current_regulation_state` — top-level columns
- `config.targets` — array of scraping targets
- `schedule` — `{"cron": "0 9 * * *", "timezone": "UTC"}` top-level column

The problem: existing endpoints return raw DB column names in snake_case. The frontend expects camelCase with specific union types (`"healthy" | "degraded"`, `"low" | "med" | "high"`, etc.). **The backend needs to shape its responses to match the frontend types exactly.**

---

## 2. The Frontend Type Contract

These types from `src/lib/types.ts` are **immutable**. The backend must produce exactly these shapes.

```ts
type Watch = {
  id: string;
  name: string;
  description: string;
  schedule: string;                    // human string: "daily", "weekly", "monthly"
  jurisdictions: string[];             // e.g. ["EU", "US-CA"]
  sources: string[];                   // e.g. ["European Commission", "Stripe"]
  status: "healthy" | "degraded";
  nextRunAt: string;                   // ISO string
  lastRunAt: string | null;
};

type ChangeEvent = {
  id: string;
  watchId: string;
  title: string;                       // = watch.name
  memo: string;                        // one-liner summary of the change
  severity: "low" | "med" | "high";   // NOT "medium"
  jurisdiction: string;               // single string
  sourceType: "regulator" | "vendor";
  createdAt: string;
  runId: string;
};

type RunStep = {
  name: string;
  status: "pending" | "running" | "done" | "retry";
  timestamp?: string;
};

type EvidenceArtifact = {
  id: string;
  type: "screenshot" | "hash" | "snapshot";
  label: string;
  url?: string;
  hash?: string;
  timestamp: string;
};

type DiffData = {
  before: string;                      // plain text, previous state
  after: string;                       // plain text, current state
  highlights: { type: "add" | "remove" | "unchanged"; text: string }[];
};

type TicketData = {
  provider: "linear" | "jira";
  url: string;
  title: string;
};

type Run = {
  id: string;
  watchId: string;
  watchName?: string;
  startedAt: string;
  endedAt: string;                     // = completed_at
  steps: RunStep[];                    // derived from agent_thoughts
  selfHealed: boolean;                 // tasks_failed > 0 && status === "completed"
  retries: number;                     // = tasks_failed
  artifacts: EvidenceArtifact[];
  diff: DiffData;
  ticket: TicketData;
  impactMemo?: string[];               // Claude memo split into bullet strings
};

type GlobePoint = {
  lat: number;
  lng: number;
  label: string;
  type: "regulator" | "vendor";
  jurisdiction: string;
};
```

---

## 3. Backend Serialization Rules

All the mapping logic lives in the backend — in a new `backend/app/serializers.py`. Routes call serializers before returning. **Zero shape translation on the frontend.**

### `Watch` serializer

> **Note:** `jurisdiction` and `source_url` are **top-level DB columns**, not nested inside `config`. `config` only contains `targets` and `schedule`.

```python
# backend/app/serializers.py

CRON_TO_LABEL = {
    "0 9 * * *": "daily",
    "0 9 * * 1": "weekly",
    "0 9 1 * *": "monthly",
    "0 * * * *":  "hourly",
}

def serialize_watch(row: dict) -> dict:
    config = row.get("config") or {}
    schedule_obj = row.get("schedule") or {}
    cron = schedule_obj.get("cron", "")
    schedule_label = CRON_TO_LABEL.get(cron, "daily")

    # Status: active + recent run succeeded → "healthy"; anything else → "degraded"
    status = "healthy" if row.get("status") == "active" else "degraded"

    # next_run_at: compute from last_run_at + schedule interval if not stored
    next_run_at = row.get("next_run_at")
    if not next_run_at and row.get("last_run_at"):
        next_run_at = _compute_next_run(row["last_run_at"], cron)

    # jurisdiction is a top-level column (string), not inside config
    jurisdiction = row.get("jurisdiction") or ""
    jurisdictions = [jurisdiction] if jurisdiction else []

    # source_url is a top-level column (string), not inside config
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
    }


import re as _re
from datetime import datetime, timedelta

def _compute_next_run(last_run_at: str, cron: str) -> str | None:
    try:
        last = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        deltas = {
            "0 9 * * *": timedelta(days=1),
            "0 9 * * 1": timedelta(weeks=1),
            "0 9 1 * *": timedelta(days=30),
            "0 * * * *": timedelta(hours=1),
        }
        delta = deltas.get(cron, timedelta(days=1))
        return (last + delta).isoformat()
    except Exception:
        return None
```

### `ChangeEvent` serializer

```python
IMPACT_TO_SEVERITY = {"low": "low", "medium": "med", "high": "high"}

def serialize_change_event(row: dict, watch: dict) -> dict:
    # jurisdiction is a top-level column on watches
    jurisdiction = (watch.get("jurisdiction") or "") if watch else ""
    # source_type derived from watch scope or default to "regulator"
    source_type = (watch.get("scope") or "regulator") if watch else "regulator"
    # Normalize: only allow "regulator" | "vendor"
    if source_type not in ("regulator", "vendor"):
        source_type = "regulator"
    return {
        "id": str(row["id"]),
        "watchId": str(row["watch_id"]),
        "title": watch.get("name", row.get("target_name", "")) if watch else row.get("target_name", ""),
        "memo": row.get("diff_summary") or "",
        "severity": IMPACT_TO_SEVERITY.get(row.get("impact_level", "medium"), "med"),
        "jurisdiction": jurisdiction,
        "sourceType": source_type,
        "createdAt": row.get("created_at", ""),
        "runId": str(row["run_id"]),
    }
```

### `Run` serializer (the complex one)

This is the most important. A single `GET /api/runs/{id}` call should return the full `Run` shape — no client-side assembly required.

```python
def serialize_run(run_row: dict, watch: dict, changes: list, evidence_bundles: list) -> dict:
    # steps: prefer run_steps_log (real-time) over agent_thoughts (post-hoc)
    steps_log = run_row.get("run_steps_log") or []
    if steps_log:
        steps = steps_log
    else:
        steps = _agent_thoughts_to_steps(run_row.get("agent_thoughts") or [])

    # Always append Diffing + Ticketing steps based on run outcome
    if run_row["status"] in ("completed", "failed"):
        steps.append({"name": "Diffing", "status": "done", "timestamp": run_row.get("completed_at")})
        steps.append({"name": "Ticketing", "status": "done", "timestamp": run_row.get("completed_at")})

    # diff: from first change with diff_details
    diff = _serialize_diff(changes[0] if changes else None)

    # ticket: from evidence_bundle or change
    ticket = _serialize_ticket(evidence_bundles, changes)

    # artifacts: from evidence bundle
    artifacts = _serialize_artifacts(evidence_bundles[0] if evidence_bundles else None)

    # impactMemo: Claude memo split into bullet strings
    impact_memo = _serialize_impact_memo(evidence_bundles[0] if evidence_bundles else None)

    return {
        "id": str(run_row["id"]),
        "watchId": str(run_row["watch_id"]),
        "watchName": watch.get("name") if watch else None,
        "startedAt": run_row["started_at"],
        "endedAt": run_row.get("completed_at") or run_row["started_at"],
        "steps": steps,
        "selfHealed": (run_row.get("tasks_failed", 0) > 0 and run_row["status"] == "completed"),
        "retries": run_row.get("tasks_failed", 0),
        "artifacts": artifacts,
        "diff": diff,
        "ticket": ticket,
        "impactMemo": impact_memo,
    }


def _serialize_run_lean(run_row: dict, watch: dict) -> dict:
    """Lean shape for list views — no diff/artifacts/ticket (expensive per-row fetches)."""
    steps_log = run_row.get("run_steps_log") or []
    steps = steps_log if steps_log else _agent_thoughts_to_steps(run_row.get("agent_thoughts") or [])
    return {
        "id": str(run_row["id"]),
        "watchId": str(run_row["watch_id"]),
        "watchName": watch.get("name") if watch else None,
        "startedAt": run_row["started_at"],
        "endedAt": run_row.get("completed_at") or run_row["started_at"],
        "steps": steps,
        "selfHealed": (run_row.get("tasks_failed", 0) > 0 and run_row["status"] == "completed"),
        "retries": run_row.get("tasks_failed", 0),
        "artifacts": [],
        "diff": {"before": "", "after": "", "highlights": []},
        "ticket": {"provider": "linear", "url": "", "title": ""},
    }


def _agent_thoughts_to_steps(thoughts: list) -> list:
    # BrowserUse AgentBrain objects → RunStep[]
    step_names = ["Searching", "Navigating", "Capturing", "Hashing"]
    if not thoughts:
        return [{"name": n, "status": "done"} for n in step_names]
    out = []
    for i, t in enumerate(thoughts[:4]):  # cap at 4 mid-steps
        name = t.get("current_state", {}).get("next_goal") or step_names[min(i, len(step_names)-1)]
        out.append({
            "name": name[:40],  # truncate long goal strings
            "status": "done",
            "timestamp": t.get("timestamp"),
        })
    return out


def _serialize_diff(change: dict | None) -> dict:
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
        [{"type": "remove", "text": d} for d in deletions[:5]] +
        [{"type": "add", "text": a} for a in additions[:5]]
    )
    return {"before": before, "after": after, "highlights": highlights}


def _serialize_ticket(evidence_bundles: list, changes: list) -> dict:
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


def _serialize_artifacts(bundle: dict | None) -> list:
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


def _serialize_impact_memo(bundle: dict | None) -> list[str] | None:
    if not bundle or not bundle.get("impact_memo"):
        return None
    memo = bundle["impact_memo"]
    import re
    parts = re.split(r"\n{2,}|(?=\d+\.\s)", memo.strip())
    return [p.strip() for p in parts if p.strip()][:6]  # max 6 bullets
```

### `GlobePoint` serializer

Derived entirely from the watches list — no separate DB table needed.

```python
JURISDICTION_COORDS = {
    "EU":    {"lat": 50.85, "lng": 4.35},
    "US":    {"lat": 38.9,  "lng": -77.0},
    "US-CA": {"lat": 37.77, "lng": -122.42},
    "California": {"lat": 37.77, "lng": -122.42},
    "UK":    {"lat": 51.51, "lng": -0.09},
    "JP":    {"lat": 35.68, "lng": 139.69},
    "AU":    {"lat": -33.86,"lng": 151.21},
    "CA":    {"lat": 45.42, "lng": -75.69},
    "DE":    {"lat": 52.52, "lng": 13.4},
    "FR":    {"lat": 48.85, "lng": 2.35},
    "Global": {"lat": 0.0, "lng": 0.0},
    "United States": {"lat": 38.9, "lng": -77.0},
}

def serialize_globe_points(watches: list) -> list:
    seen = set()
    points = []
    for w in watches:
        # jurisdiction is a top-level column, not inside config
        jurisdiction = w.get("jurisdiction") or ""
        source_url = w.get("source_url") or ""
        # Normalize source_type from scope field or default
        scope = w.get("scope") or "regulator"
        source_type = scope if scope in ("regulator", "vendor") else "regulator"

        key = f"{jurisdiction}:{w['name']}"
        if key not in seen and jurisdiction in JURISDICTION_COORDS:
            seen.add(key)
            points.append({
                "lat": JURISDICTION_COORDS[jurisdiction]["lat"],
                "lng": JURISDICTION_COORDS[jurisdiction]["lng"],
                "label": w["name"],
                "type": source_type,
                "jurisdiction": jurisdiction,
            })
    return points
```

---

## 4. New Backend Endpoints to Add

The existing routes return raw DB shapes. We need to update existing responses AND add missing ones. All changes are **additive** — no existing endpoint signatures change.

### 4a. Update `GET /api/watches` and `GET /api/watches/{id}`

Change the `_watch_to_response` helper in `routes.py` to call `serialize_watch()` instead of the current hand-rolled dict.

```python
# routes.py
from app.serializers import serialize_watch, serialize_globe_points

@router.get("/watches")
async def list_watches():
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    # ... existing count queries ...
    return [serialize_watch(w) for w in watches]

@router.get("/globe-points")
async def globe_points():
    """Derive globe data from real watches — replaces hardcoded mock globePoints."""
    svc = WatchService()
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    return {"points": serialize_globe_points(watches)}
```

### 4b. New: `GET /api/changes`

Changes list, shaped as `ChangeEvent[]`. Used by `ChangesCard` and `/history` page.

```python
@router.get("/changes")
async def list_changes(limit: int = 50, watch_id: Optional[str] = None):
    from app.db import get_supabase
    from app.serializers import serialize_change_event
    db = get_supabase()
    q = db.table("changes").select("*, watches(name, jurisdiction, scope)").order("created_at", desc=True).limit(limit)
    if watch_id:
        q = q.eq("watch_id", watch_id)
    r = await asyncio.to_thread(lambda: q.execute())

    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(serialize_change_event(row, watch))
    return {"changes": result}
```

### 4c. New: `GET /api/watches/{watch_id}/changes`

Scoped version for watch detail page — reuses the logic above with a filter.

```python
@router.get("/watches/{watch_id}/changes")
async def get_watch_changes(watch_id: str):
    return await list_changes(watch_id=watch_id)
```

### 4d. Update `GET /api/runs/{run_id}` — return full `Run` shape

The existing endpoint returns a thin summary. Update it to return the complete `Run` type that the frontend expects. Fetch changes + evidence in the same call.

```python
@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    from app.db import get_supabase
    from app.serializers import serialize_run
    svc = WatchService()
    run_row = await svc.get_run(run_id)
    if not run_row:
        raise HTTPException(404)
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
```

### 4e. Update `GET /api/runs/recent` — return lean `Run[]` shape

```python
@router.get("/runs/recent")
async def recent_runs(limit: int = 50):
    from app.db import get_supabase
    from app.serializers import _serialize_run_lean
    db = get_supabase()
    r = await asyncio.to_thread(
        lambda: db.table("watch_runs").select("*, watches(name, jurisdiction, scope)").order("started_at", desc=True).limit(limit).execute()
    )
    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(_serialize_run_lean(row, watch))
    return {"runs": result}
```

### 4f. New: `GET /api/watches/{watch_id}/runs`

The watch detail page lists runs for a specific watch. This is distinct from the existing `/history` endpoint (which returns raw shapes). Returns lean `Run[]`.

```python
@router.get("/watches/{watch_id}/runs")
async def get_watch_runs(watch_id: str, limit: int = 50):
    from app.serializers import _serialize_run_lean
    svc = WatchService()
    runs = await svc.get_watch_runs(watch_id, limit=limit)
    watch = await svc.get_watch(watch_id)
    return {"runs": [_serialize_run_lean(r, watch or {}) for r in runs]}
```

### 4g. New: `GET /api/globe-points`

Already described in §4a. New endpoint that returns `GlobePoint[]` derived from watches.

### 4h. Update `POST /api/watches/{id}/run` — return `run_id` immediately

Currently returns `{"status": "queued", ...}` without a `run_id`. Add `run_id` so the frontend can immediately poll that specific run. `svc.create_run()` already exists in `WatchService`.

```python
@router.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, background_tasks: BackgroundTasks):
    svc = WatchService()
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(404)
    # Create the run row NOW (before backgrounding) so we have the ID
    run = await svc.create_run(watch_id, status="running")
    run_id = str(run["id"])
    background_tasks.add_task(_execute_watch_background, watch_id)
    return {"status": "queued", "watch_id": watch_id, "run_id": run_id}
```

---

## 5. New Database Columns to Add

All additive — no existing columns removed or renamed.

### `watch_runs` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `agent_summary` | `text` | `null` | Already exists in DB — verify migration |
| `agent_thoughts` | `jsonb` | `null` | Already exists in DB — verify migration |
| `run_steps_log` | `jsonb` | `[]` | Real-time step-by-step log written during execution; powers polling |

### `changes` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `linear_ticket_url` | `text` | `null` | Surface ticket URL for direct access |
| `jira_ticket_url` | `text` | `null` | Same |

### `evidence_bundles` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `linear_ticket_url` | `text` | `null` | Store ticket URL here for direct join |
| `ticket_title` | `text` | `null` | Linear/Jira ticket title |

### `watches` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `next_run_at` | `timestamptz` | `null` | Written by orchestrator after each run; `serialize_watch` returns it |

---

## 6. Frontend Changes (Minimal)

**The frontend barely changes.** No types change, no run/evidence components change. Three things happen:

### 6a. Replace `src/lib/api.ts`

The existing `api.ts` has raw snake_case types (`Watch` with `next_run_at`, `WatchRun`, etc.) that conflict with `types.ts`. **Replace the entire file** with this typed API client:

```ts
// src/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

import type { Watch, ChangeEvent, Run, GlobePoint } from "./types";

export const api = {
  watches: {
    list: ():             Promise<Watch[]>      => get<Watch[]>("/api/watches"),
    get:  (id: string):  Promise<Watch>        => get(`/api/watches/${id}`),
    create: (body: CreateWatchBody): Promise<Watch> => post("/api/watches", body),
    run: (id: string):   Promise<{ run_id: string; watch_id: string; status: string }> =>
      post(`/api/watches/${id}/run`),
    runs: (id: string):    Promise<Run[]>        =>
      get<{runs: Run[]}>(`/api/watches/${id}/runs`).then(r => r.runs),
    changes: (id: string): Promise<ChangeEvent[]> =>
      get<{changes: ChangeEvent[]}>(`/api/watches/${id}/changes`).then(r => r.changes),
  },
  runs: {
    recent: (): Promise<Run[]>      => get<{runs: Run[]}>("/api/runs/recent").then(r => r.runs),
    get: (id: string): Promise<Run> => get(`/api/runs/${id}`),
  },
  changes: {
    list: (limit = 50): Promise<ChangeEvent[]> =>
      get<{changes: ChangeEvent[]}>(`/api/changes?limit=${limit}`).then(r => r.changes),
  },
  globe: {
    points: (): Promise<GlobePoint[]> =>
      get<{points: GlobePoint[]}>("/api/globe-points").then(r => r.points),
  },
  onboard: {
    start: (productUrl: string): Promise<{ job_id: string }> =>
      post("/api/analyze-product", { product_url: productUrl }),
    status: (jobId: string): Promise<OnboardStatus> =>
      get<OnboardStatus>(`/api/analyze-product/${jobId}`),
  },
};

export type CreateWatchBody = {
  name: string;
  description?: string;
  config: {
    targets: Array<{
      name: string;
      starting_url?: string;
      search_query?: string;
      extraction_instructions: string;
    }>;
  };
};

export type OnboardStatus = {
  status: "pending" | "running" | "completed" | "failed";
  product_url?: string;
  risks_identified?: number;       // count of identified risks
  watches_created?: number;        // count of watches created
  watches?: Watch[];               // serialized Watch[] (only on "completed")
  product_info?: {
    content_preview: string;
    url: string;
  };
  error?: string;
};
```

### 6b. Add `frontend/.env.local`

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 6c. Install `swr`

```bash
npm install swr
```

### 6d. Add `watches` prop to `WatchesCard`

`WatchesCard` currently calls `getWatchesByJurisdiction()` internally from mockData — it has no external `watches` prop. Add an optional prop so the dashboard can pass real data:

```diff
// src/components/dashboard/WatchesCard.tsx
- import { getWatchesByJurisdiction } from "@/lib/mockData";
+ import { getWatchesByJurisdiction } from "@/lib/mockData";
+ import type { Watch } from "@/lib/types";

  type WatchesCardProps = {
    activeJurisdiction: string | null;
    onRunAll: () => void;
+   watches?: Watch[];   // if provided, skip mock lookup
  };

  export function WatchesCard({ activeJurisdiction, onRunAll, watches: watchesProp }: WatchesCardProps) {
-   const watches = getWatchesByJurisdiction(activeJurisdiction);
+   const allWatches = watchesProp ?? getWatchesByJurisdiction(null);
+   const watches = activeJurisdiction
+     ? allWatches.filter(w => w.jurisdictions.includes(activeJurisdiction))
+     : allWatches;
```

---

## 7. Page-by-Page Wiring

Each page gets the same treatment: delete the mock import, add `useSWR`.

### `/app` — Dashboard

```diff
- import { changeEvents, globePoints } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";
```

```ts
// Replace mock data refs:
const { data: changes = [], mutate: mutateChanges } = useSWR("changes", () => api.changes.list(20));
const { data: watches = [] } = useSWR("watches", api.watches.list);
const { data: globePoints = [] } = useSWR("globe", api.globe.points);
const { data: recentRuns = [] } = useSWR("runs/recent", api.runs.recent);
```

Pass `watches` to `WatchesCard` (uses the new prop from §6d):
```tsx
<WatchesCard
  watches={watches}
  activeJurisdiction={activeJurisdiction}
  onRunAll={runAll}
/>
```

**`runAll` button:** Replace the fake animation with a real call. The step animation logic already exists and works — just drive it off a real `run_id` poll:

```ts
const runAll = React.useCallback(async () => {
  if (isRunning || watches.length === 0) return;
  setIsRunning(true);
  setCurrentRunSteps(RUN_STEP_NAMES.map(name => ({ name, status: "pending" as const })));

  const { run_id } = await api.watches.run(watches[0].id);

  // Poll run until complete; update steps from run.steps
  const poll = setInterval(async () => {
    try {
      const run = await api.runs.get(run_id);
      setCurrentRunSteps(run.steps);
      if (run.endedAt && run.endedAt !== run.startedAt) {
        clearInterval(poll);
        setIsRunning(false);
        mutateChanges();   // refresh changes card
      }
    } catch {
      clearInterval(poll);
      setIsRunning(false);
    }
  }, 2000);
}, [isRunning, watches, mutateChanges]);
```

**`RunsCard` completion rate** — compute from real data:
```ts
const completionRate = recentRuns.length
  ? Math.round(recentRuns.filter(r => !r.selfHealed).length / recentRuns.length * 100)
  : 98;
```

**`ChangesCard`** — change from state to SWR data directly (no more `setChanges`):
```diff
- const [changes, setChanges] = React.useState<ChangeEvent[]>(changeEvents);
+ // changes already comes from useSWR above

  <ChangesCard
    activeJurisdiction={activeJurisdiction}
    changes={changes}
-   setChanges={setChanges}
  />
```

**Globe:** `JurisdictionGlobe` receives `points={globePoints}` — no component change, just real data.

### `/watches` — Watch List

```diff
- import { watches } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: watches = [] } = useSWR("watches", api.watches.list);
```

Component renders `watches` — unchanged.

### `/watches/[id]` — Watch Detail

```diff
- import { watches, runs } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: watch } = useSWR(`watch/${id}`, () => api.watches.get(id));
+ const { data: watchRuns = [] } = useSWR(`watch/${id}/runs`, () => api.watches.runs(id));
```

Replace `watches.find(...)` with the `watch` SWR result; replace `runs.filter(...)` with `watchRuns`.

### `/app/run/[id]` — Run Detail

```diff
- import { getRunById } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

- const run = id ? getRunById(id) : null;
+ const { data: run } = useSWR(id ? `run/${id}` : null, () => api.runs.get(id!));
```

`run` already has the full `Run` shape. **Nothing in `RunTimeline`, `DiffViewer`, or `EvidenceBundle` changes.** Add loading state:
```ts
if (!run) return <div className="p-12 text-center text-muted-foreground">Loading…</div>;
```

### `/history` — History Page

```diff
- import { runs } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: runs = [] } = useSWR("runs/recent", api.runs.recent);
```

---

## 8. Real-Time Run Progress

When "Run All" or "Run now" fires, the frontend has a `run_id` and needs to know when steps complete.

### Option A: Poll (ship now, ~1 hour)

`GET /api/runs/{id}` returns the current `run.steps` from `run_steps_log`. The orchestrator writes step updates to `run_steps_log` as it executes.

**Orchestrator change** (in `orchestrator.py`) — add step-writing after each target completes:

```python
# In orchestrator.py, after each target task resolves:
async def _append_run_step(self, run_id: str, step: dict):
    from app.db import get_supabase
    db = get_supabase()
    run = await self.watch_service.get_run(run_id)
    steps = (run or {}).get("run_steps_log") or []
    steps.append(step)
    await asyncio.to_thread(
        lambda: db.table("watch_runs").update({"run_steps_log": steps}).eq("id", run_id).execute()
    )
```

Call it after each browser-use task completes:
```python
await self._append_run_step(run_id, {
    "name": target.get("name", "Capturing"),
    "status": "done",
    "timestamp": datetime.utcnow().isoformat(),
})
```

Frontend poll (already shown in §7 Dashboard `runAll`):
```ts
const poll = setInterval(async () => {
  const run = await api.runs.get(run_id);
  setCurrentRunSteps(run.steps);
  if (run.endedAt !== run.startedAt) {
    clearInterval(poll);
    setIsRunning(false);
    mutateChanges();
  }
}, 2000);
```

### Option B: SSE (later, cleaner)

Add to `routes.py`:

```python
from fastapi.responses import StreamingResponse
import json

@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str):
    async def events():
        while True:
            svc = WatchService()
            run = await svc.get_run(run_id)
            steps = run.get("run_steps_log") or []
            yield f"data: {json.dumps({'steps': steps, 'status': run['status']})}\n\n"
            if run["status"] in ("completed", "failed"):
                break
            await asyncio.sleep(1.5)
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

Frontend hook (replaces poll):
```ts
const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function useRunStream(runId: string | null, onUpdate: (steps: RunStep[]) => void) {
  useEffect(() => {
    if (!runId) return;
    const es = new EventSource(`${BASE}/api/runs/${runId}/stream`);
    es.onmessage = (e) => {
      const { steps, status } = JSON.parse(e.data);
      onUpdate(steps);
      if (status === "completed" || status === "failed") es.close();
    };
    return () => es.close();
  }, [runId]);
}
```

---

## 9. AI Onboarding Flow

The **"wow" feature**. User pastes their product URL, the AI identifies every compliance risk, and watches are auto-created.

### Backend: Already Implemented

The onboarding pipeline already fully exists:
- **`backend/app/services/product_analyzer.py`** — `ProductAnalyzer` class handles all three stages: scraping (BrowserUse), risk analysis (Claude), and watch creation
- **`POST /api/analyze-product`** — queues the job, returns `job_id` immediately
- **`GET /api/analyze-product/{job_id}`** — polls job status

**Do not create a new `onboarding_service.py`** — that logic is already in `ProductAnalyzer`.

The only backend addition needed: the job response should include serialized `watches` in the camelCase `Watch[]` shape. Update `_run_analysis_background` in `routes.py`:

```diff
# In routes.py _run_analysis_background:
+ from app.serializers import serialize_watch
  _analysis_jobs[job_id].update({
      "status": "completed",
      ...
-     "watches": [_watch_to_response(w) for w in result["watches"]],
+     "watches": [serialize_watch(w) for w in result["watches"]],
  })
```

### Frontend: Onboarding Modal

Add to `CommandBar` — that button is already there. Wire it to open a modal:

```
┌─────────────────────────────────────────────────────┐
│  Analyze your product for compliance risks           │
│                                                      │
│  Product URL  [https://yourapp.com _______________]  │
│                                                      │
│  [Analyze →]                                         │
└─────────────────────────────────────────────────────┘
```

Loading state (poll `GET /api/analyze-product/{job_id}` every 2s via `api.onboard.status(jobId)`):
```
┌─────────────────────────────────────────────────────┐
│  Analyzing yourapp.com...                            │
│                                                      │
│  ⟳ Running analysis...                              │
│  ○ Creating watches                                  │
└─────────────────────────────────────────────────────┘
```

Completed state — `status.watches` contains the created `Watch[]`:
```
┌─────────────────────────────────────────────────────┐
│  14 compliance risks identified                      │
│  14 watches created                                  │
│                                                      │
│  [Go to Watches →]                                   │
└─────────────────────────────────────────────────────┘
```

On completion: call `mutate("watches")` to refresh the watches list, then navigate to `/watches`.

---

## 10. Implementation Order

Each phase is independently deployable and testable.

### Phase 1 — Backend serializers (3-4 hours)
1. Create `backend/app/serializers.py` with all serializers from §3
2. Run DB migration: add `run_steps_log` to `watch_runs`; add ticket URL columns to `changes` and `evidence_bundles`; add `next_run_at` to `watches`
3. Update `list_watches` and `get_watch` in routes.py to call `serialize_watch()`
4. Add `GET /api/globe-points` → `serialize_globe_points()`
5. Test `GET /api/watches` returns `Watch[]` shape exactly

### Phase 2 — New read endpoints (2-3 hours)
6. Add `GET /api/changes` → `ChangeEvent[]` shape
7. Add `GET /api/watches/{id}/changes`
8. Add `GET /api/watches/{id}/runs` → lean `Run[]`
9. Update `GET /api/runs/{id}` to fetch changes+evidence and return full `Run` shape
10. Update `GET /api/runs/recent` to return lean `Run[]`

### Phase 3 — Frontend wiring, read-only (2-3 hours)
11. Add `frontend/.env.local` + install `swr`
12. Replace `src/lib/api.ts` with the new typed client from §6a
13. Add `watches` prop to `WatchesCard` (§6d)
14. Wire `/watches` page — replace mock, verify real data renders
15. Wire `/watches/[id]` page
16. Wire `/history` page
17. Wire `/app` dashboard (watches card, changes card, globe)

### Phase 4 — Run detail (1-2 hours)
18. Wire `/app/run/[id]` — replace `getRunById` with `useSWR`
19. Add loading state for when `run` is `null`
20. Verify `RunTimeline`, `DiffViewer`, `EvidenceBundle` all render correctly with real data

### Phase 5 — Live run triggering (2-3 hours)
21. Add step-writing to orchestrator (§8 Option A)
22. Update `POST /api/watches/{id}/run` to return `run_id` (§4h)
23. Replace fake animation in Dashboard `runAll` with real poll loop
24. Add "Run now" button wiring on `/watches/[id]`

### Phase 6 — Onboarding wiring (1-2 hours)
25. Update `_run_analysis_background` to use `serialize_watch()` for the `watches` field
26. Add onboarding modal component to frontend
27. Wire `CommandBar` "Analyze product" button to open modal
28. Poll `GET /api/analyze-product/{job_id}` for progress, navigate to `/watches` on completion

### Phase 7 — Polish + SSE (optional, ½ day)
29. Replace poll with SSE stream endpoint (§8 Option B)
30. Add `useRunStream` hook
31. Handle error states (run failed, watch not found, API down)
