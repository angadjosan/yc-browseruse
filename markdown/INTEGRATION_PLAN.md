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

### Frontend (branch: `frontend`)

Every page reads from `src/lib/mockData.ts`. Nothing hits the network. The frontend has beautiful, well-structured types in `src/lib/types.ts` — those types become the law.

| Page | Mock source used | Real endpoint needed |
|------|----------------|---------------------|
| `/app` (Dashboard) | `watches`, `changeEvents`, `globePoints` | `GET /api/watches`, `GET /api/changes` |
| `/watches` | `watches` | `GET /api/watches` |
| `/watches/[id]` | `watches`, `runs` | `GET /api/watches/{id}`, `GET /api/watches/{id}/runs` |
| `/app/run/[id]` | `runs` via `getRunById` | `GET /api/runs/{id}` (new full shape) |
| `/history` | `runs` | `GET /api/runs/recent` |

The `CommandBar` "Run All" button runs a fake-progress animation loop — no API call. The `WatchesCard` `onRunAll` prop feeds this. That's the main interactive piece to wire up.

### Backend (branch: `main` + `ai-shit`)

Fully wired FastAPI + Supabase pipeline. Existing endpoints:

```
POST   /api/watches                  create watch
GET    /api/watches                  list watches
GET    /api/watches/{id}             single watch
POST   /api/watches/{id}/run         trigger run (backgrounded)
GET    /api/watches/{id}/history     runs for a watch
GET    /api/runs/recent              all recent runs
GET    /api/runs/{id}                single run
GET    /api/evidence                 list evidence bundles
GET    /api/evidence/{id}            single evidence bundle
GET    /api/health                   dependency status
```

**AI pipeline writes per run:**
- `watch_runs.agent_summary` — Claude-written one-liner
- `watch_runs.agent_thoughts` — BrowserUse `AgentBrain` objects (step reasoning)
- `snapshots` — raw scraped text + hash + URL per target
- `changes.diff_details` — `{text_diff: {additions, deletions}, semantic_diff: {summary, impact_level, key_changes, recommended_actions}}`
- `evidence_bundles` — Claude impact memo, screenshots, content hashes, HMAC signature

The problem: the existing endpoints return raw DB column names in snake_case with DB-native types. The frontend expects camelCase with specific union types (`"healthy" | "degraded"`, `"low" | "med" | "high"`, etc.). **The backend needs to shape its responses to match the frontend types exactly.**

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

```python
# backend/app/serializers.py

CRON_TO_LABEL = {
    "0 9 * * *": "daily",
    "0 9 * * 1": "weekly",
    "0 9 1 * *": "monthly",
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

    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description") or "",
        "schedule": schedule_label,
        "jurisdictions": config.get("jurisdictions") or [],
        "sources": config.get("sources") or [],
        "status": status,
        "nextRunAt": next_run_at or "",
        "lastRunAt": row.get("last_run_at"),
    }
```

### `ChangeEvent` serializer

```python
IMPACT_TO_SEVERITY = {"low": "low", "medium": "med", "high": "high"}

def serialize_change_event(row: dict, watch: dict) -> dict:
    watch_config = (watch.get("config") or {}) if watch else {}
    jurisdictions = watch_config.get("jurisdictions") or []
    return {
        "id": str(row["id"]),
        "watchId": str(row["watch_id"]),
        "title": watch.get("name", row.get("target_name", "")) if watch else row.get("target_name", ""),
        "memo": row.get("diff_summary") or "",
        "severity": IMPACT_TO_SEVERITY.get(row.get("impact_level", "medium"), "med"),
        "jurisdiction": jurisdictions[0] if jurisdictions else "",
        "sourceType": watch_config.get("source_type", "regulator"),
        "createdAt": row.get("created_at", ""),
        "runId": str(row["run_id"]),
    }
```

### `Run` serializer (the complex one)

This is the most important. A single `GET /api/runs/{id}` call should return the full `Run` shape — no client-side assembly required.

```python
def serialize_run(run_row: dict, watch: dict, changes: list, evidence_bundles: list) -> dict:
    # steps: derive from agent_thoughts
    steps = _agent_thoughts_to_steps(run_row.get("agent_thoughts") or [])
    # Always append Diffing + Ticketing steps based on run outcome
    if run_row["status"] in ("completed", "failed"):
        steps.append({"name": "Diffing", "status": "done" if changes else "done", "timestamp": run_row.get("completed_at")})
        steps.append({"name": "Ticketing", "status": "done" if _has_ticket(changes, evidence_bundles) else "done"})

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

def _agent_thoughts_to_steps(thoughts: list) -> list:
    # BrowserUse AgentBrain objects → RunStep[]
    # Each thought has action_name, thought text, timestamp
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

    # before/after: use semantic summary sentences or raw additions/deletions
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
    # Try evidence bundle first, then changes
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
    # Split on double newline or numbered sections into bullet strings
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
    "UK":    {"lat": 51.51, "lng": -0.09},
    "JP":    {"lat": 35.68, "lng": 139.69},
    "AU":    {"lat": -33.86,"lng": 151.21},
    "CA":    {"lat": 45.42, "lng": -75.69},
    "DE":    {"lat": 52.52, "lng": 13.4},
    "FR":    {"lat": 48.85, "lng": 2.35},
}

def serialize_globe_points(watches: list) -> list:
    seen = set()
    points = []
    for w in watches:
        config = w.get("config") or {}
        jurisdictions = config.get("jurisdictions") or []
        sources = config.get("sources") or []
        source_type = config.get("source_type", "regulator")
        for j in jurisdictions:
            key = f"{j}:{sources[0] if sources else w['name']}"
            if key not in seen and j in JURISDICTION_COORDS:
                seen.add(key)
                points.append({
                    "lat": JURISDICTION_COORDS[j]["lat"],
                    "lng": JURISDICTION_COORDS[j]["lng"],
                    "label": sources[0] if sources else w["name"],
                    "type": source_type,
                    "jurisdiction": j,
                })
    return points
```

---

## 4. New Backend Endpoints to Add

The existing routes return raw DB shapes. We need to update existing responses AND add missing ones. All changes are **additive** — no existing endpoint signatures change.

### 4a. Update `GET /api/watches` and `GET /api/watches/{id}`

Change the `_watch_to_response` helper in `routes.py` to call `serialize_watch()` instead of the current hand-rolled dict. This is the only change to existing endpoints.

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
    watches = await svc.list_watches(DEFAULT_ORG_ID)
    return {"points": serialize_globe_points(watches)}
```

### 4b. New: `GET /api/changes`

Changes list, shaped as `ChangeEvent[]`. Used by `ChangesCard` and `/history` page.

```python
@router.get("/changes")
async def list_changes(limit: int = 50, watch_id: Optional[str] = None):
    db = get_supabase()
    q = db.table("changes").select("*, watches(name, config)").order("created_at", desc=True).limit(limit)
    if watch_id:
        q = q.eq("watch_id", watch_id)
    r = q.execute()

    result = []
    for row in (r.data or []):
        watch = row.pop("watches", None) or {}
        result.append(serialize_change_event(row, watch))
    return {"changes": result}
```

### 4c. New: `GET /api/watches/{watch_id}/changes`

Scoped version for watch detail page.

```python
@router.get("/watches/{watch_id}/changes")
async def get_watch_changes(watch_id: str):
    # reuse list_changes logic with watch_id filter
    ...
```

### 4d. Update `GET /api/runs/{run_id}` — return full `Run` shape

The existing endpoint returns a thin summary. Update it to return the complete `Run` type that the frontend expects. Fetch changes + evidence in the same call.

```python
@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    db = get_supabase()
    run_row = await svc.get_run(run_id)
    if not run_row:
        raise HTTPException(404)
    watch = await svc.get_watch(str(run_row["watch_id"])) if run_row.get("watch_id") else None

    # Fetch changes for this run
    changes_r = db.table("changes").select("*").eq("run_id", run_id).order("created_at").execute()
    changes = changes_r.data or []

    # Fetch evidence bundles for this run
    evidence_r = db.table("evidence_bundles").select("*").eq("run_id", run_id).order("created_at").execute()
    evidence = evidence_r.data or []

    return serialize_run(run_row, watch, changes, evidence)
```

### 4e. Update `GET /api/runs/recent` — return `Run[]` shape

Same as above but for the list. The history page just needs `id, watchId, watchName, startedAt, endedAt, selfHealed, retries, steps` — the list view doesn't need full diff/artifacts, so return a lean version.

```python
@router.get("/runs/recent")
async def recent_runs(limit: int = 50):
    db = get_supabase()
    r = db.table("watch_runs").select("*, watches(name)").order("started_at", desc=True).limit(limit).execute()
    result = []
    for row in (r.data or []):
        watch = {"name": (row.pop("watches") or {}).get("name")}
        # Lean shape for list view — no diff/artifacts/ticket (expensive to fetch for 50 rows)
        result.append({
            "id": str(row["id"]),
            "watchId": str(row["watch_id"]),
            "watchName": watch["name"],
            "startedAt": row["started_at"],
            "endedAt": row.get("completed_at") or row["started_at"],
            "steps": _agent_thoughts_to_steps(row.get("agent_thoughts") or []),
            "selfHealed": (row.get("tasks_failed", 0) > 0 and row["status"] == "completed"),
            "retries": row.get("tasks_failed", 0),
            "artifacts": [],
            "diff": {"before": "", "after": "", "highlights": []},
            "ticket": {"provider": "linear", "url": "", "title": ""},
        })
    return {"runs": result}
```

### 4f. New: `GET /api/watches/{watch_id}/runs`

The watch detail page lists runs for a specific watch. Currently this is `GET /api/watches/{id}/history` but it returns a summary shape. Add this alias that returns lean `Run[]`.

```python
@router.get("/watches/{watch_id}/runs")
async def get_watch_runs(watch_id: str, limit: int = 50):
    runs = await svc.get_watch_runs(watch_id, limit=limit)
    watch = await svc.get_watch(watch_id)
    return {"runs": [_serialize_run_lean(r, watch) for r in runs]}
```

### 4g. New: `POST /api/onboard` + `GET /api/onboard/{job_id}`

The AI onboarding flow — see §9.

### 4h. Update `POST /api/watches/{id}/run` — return `run_id` immediately

Currently returns `{"status": "queued", ...}`. Add `run_id` so the frontend can immediately poll/stream that specific run.

```python
# In routes.py
async def _execute_watch_background(watch_id: str, run_id: str):
    orchestrator = OrchestratorEngine()
    await orchestrator.execute_watch(watch_id)

@router.post("/watches/{watch_id}/run")
async def run_watch_now(watch_id: str, background_tasks: BackgroundTasks):
    watch = await svc.get_watch(watch_id)
    if not watch:
        raise HTTPException(404)
    # Create the run row NOW (before backgrounding) so we have the ID
    run = await svc.create_run(watch_id, status="running")
    run_id = str(run["id"])
    background_tasks.add_task(_execute_watch_background, watch_id, run_id)
    return {"status": "queued", "watch_id": watch_id, "run_id": run_id}
```

---

## 5. New Database Columns to Add

All additive — no existing columns removed or renamed.

### `watch_runs` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `agent_summary` | `text` | `null` | Already in ai-shit branch — migrate to main |
| `agent_thoughts` | `jsonb` | `null` | Already in ai-shit branch — migrate to main |
| `run_steps_log` | `jsonb` | `[]` | Real-time step-by-step log written during execution; powers the SSE stream |

### `changes` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `linear_ticket_url` | `text` | `null` | Currently buried in evidence_bundles; surface here for direct access |
| `jira_ticket_url` | `text` | `null` | Same |

### `evidence_bundles` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `linear_ticket_url` | `text` | `null` | Store ticket URL here too for direct join |
| `ticket_title` | `text` | `null` | Linear/Jira ticket title |

### `watches` table

| Column | Type | Default | Reason |
|--------|------|---------|--------|
| `next_run_at` | `timestamptz` | `null` | Written by orchestrator after each run; `serialize_watch` returns it |

---

## 6. Frontend Changes (Minimal)

**The frontend barely changes.** No types change, no components change. Only two things happen:

### 6a. Add `src/lib/api.ts`

A single thin typed fetch wrapper. Returns exactly the shapes from `types.ts` because the backend now outputs them directly.

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
    list: ():    Promise<Watch[]>      => get<{watches?: Watch[]} | Watch[]>("/api/watches").then(r => Array.isArray(r) ? r : r.watches ?? []),
    get:  (id:string): Promise<Watch> => get(`/api/watches/${id}`),
    create: (body: CreateWatchBody): Promise<Watch> => post("/api/watches", body),
    run: (id: string): Promise<{ run_id: string }> => post(`/api/watches/${id}/run`),
    runs: (id: string): Promise<Run[]> => get<{runs: Run[]}>(`/api/watches/${id}/runs`).then(r => r.runs),
    changes: (id: string): Promise<ChangeEvent[]> => get<{changes: ChangeEvent[]}>(`/api/watches/${id}/changes`).then(r => r.changes),
  },
  runs: {
    recent: (): Promise<Run[]>       => get<{runs: Run[]}>("/api/runs/recent").then(r => r.runs),
    get: (id: string): Promise<Run>  => get(`/api/runs/${id}`),
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
      post("/api/onboard", { product_url: productUrl }),
    status: (jobId: string) => get<OnboardStatus>(`/api/onboard/${jobId}`),
  },
};

export type CreateWatchBody = {
  name: string;
  description?: string;
  config: {
    jurisdictions?: string[];
    sources?: string[];
    source_type?: "regulator" | "vendor";
    targets: Array<{
      name: string;
      starting_url?: string;
      search_query?: string;
      extraction_instructions: string;
    }>;
  };
};

export type OnboardStatus = {
  status: "processing" | "completed" | "failed";
  stage?: "scraping" | "analyzing" | "creating_watches";
  risks?: OnboardRisk[];
  watches_created?: Watch[];
};

export type OnboardRisk = {
  regulation_title: string;
  why_its_a_risk: string;
  jurisdiction: string;
  source_type: "regulator" | "vendor";
  impact_level: "low" | "med" | "high";
  source_url: string;
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

That's it for new files. Everything else is surgical replacements in pages.

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
const { data: changes = [] } = useSWR("changes", () => api.changes.list(20));
const { data: watches = [] } = useSWR("watches", api.watches.list);
const { data: globePoints = [] } = useSWR("globe", api.globe.points);
const { data: recentRuns = [] } = useSWR("runs/recent", api.runs.recent);
```

**`runAll` button:** Replace the fake animation with a real call. The step animation logic already exists and works — just drive it off a real `run_id` poll instead of a `setTimeout` chain.

```ts
const runAll = useCallback(async () => {
  if (isRunning) return;
  setIsRunning(true);
  setCurrentRunSteps(RUN_STEP_NAMES.map(name => ({ name, status: "pending" })));

  // Trigger first watch (or all) — get run_id back
  const { run_id } = await api.watches.run(watches[0].id);

  // Poll run until complete; update steps from run.steps
  const poll = setInterval(async () => {
    const run = await api.runs.get(run_id);
    setCurrentRunSteps(run.steps);
    if (run.endedAt && run.endedAt !== run.startedAt) {
      clearInterval(poll);
      setIsRunning(false);
      mutate("changes");   // refresh changes card
      mutate("watches");   // refresh watches card
    }
  }, 2000);
}, [isRunning, watches]);
```

**Globe:** `JurisdictionGlobe` receives `points={globePoints}` — no component change, just real data.

**`RunsCard`:** Already accepts `completionRate` and `falsePositiveRate` as props. Compute from `recentRuns`:
```ts
const completionRate = recentRuns.length
  ? Math.round(recentRuns.filter(r => !r.selfHealed).length / recentRuns.length * 100)
  : 98;
```

### `/watches` — Watch List

```diff
- import { watches } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: watches = [] } = useSWR("watches", api.watches.list);
```

Component receives `watches` — unchanged.

### `/watches/[id]` — Watch Detail

```diff
- import { watches, runs } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: watch } = useSWR(`watch/${id}`, () => api.watches.get(id));
+ const { data: watchRuns = [] } = useSWR(`watch/${id}/runs`, () => api.watches.runs(id));
```

The page already renders `watch` and `watchRuns` — no component logic changes. The existing `runs.filter(r => r.watchId === watch.id)` becomes the real API result.

### `/app/run/[id]` — Run Detail

```diff
- import { getRunById } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

- const run = id ? getRunById(id) : null;
+ const { data: run } = useSWR(id ? `run/${id}` : null, () => api.runs.get(id!));
```

`run` already has the full `Run` shape (steps, diff, ticket, artifacts, impactMemo) because the backend serializes it that way. Components receive exactly what they already expect. **Nothing in `RunTimeline`, `DiffViewer`, or `EvidenceBundle` changes.**

Loading state (currently missing from mock): add a check for `if (!run) return <LoadingSpinner />`.

### `/history` — History Page

```diff
- import { runs } from "@/lib/mockData";
+ import useSWR from "swr";
+ import { api } from "@/lib/api";

+ const { data: runs = [] } = useSWR("runs/recent", () => api.runs.recent());
```

---

## 8. Real-Time Run Progress

When "Run All" or "Run now" fires, the frontend has a `run_id` and needs to know when steps complete. The existing animated step loop is perfect — just feed it real data.

### Option A: Poll (ship now, ~1 hour)

`GET /api/runs/{id}` returns the current `run.steps` from `run_steps_log`. The orchestrator writes step updates to `run_steps_log` as it executes. Frontend polls every 2s.

**Orchestrator change** (in `execute_watch`): after each `spawn_handler` resolves, write a step entry:

```python
# In orchestrator.py, inside the spawn_handler:
async def spawn_handler(tool_input):
    result = await self.execute_browser_use_task(task)
    # Write step update to DB
    await self._append_run_step(run_id, {
        "name": task.target_name,
        "status": "done",
        "timestamp": datetime.utcnow().isoformat(),
    })
    return result

async def _append_run_step(self, run_id: str, step: dict):
    run = await self.watch_service.get_run(run_id)
    steps = run.get("run_steps_log") or []
    steps.append(step)
    self.db.table("watch_runs").update({"run_steps_log": steps}).eq("id", run_id).execute()
```

`serialize_run` reads `run_steps_log` before `agent_thoughts` for steps (more real-time).

Frontend poll:
```ts
// In dashboard runAll handler
const poll = setInterval(async () => {
  const run = await api.runs.get(run_id);
  setCurrentRunSteps(run.steps);   // run.steps comes from run_steps_log
  if (run.endedAt !== run.startedAt) {
    clearInterval(poll);
    setIsRunning(false);
    mutate("changes");
  }
}, 2000);
```

### Option B: SSE (later, cleaner)

Add to `routes.py`:

```python
from fastapi.responses import StreamingResponse

@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str):
    async def events():
        while True:
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

This is the **"wow" feature** from `ai_workflow.md`. User pastes their product URL, Claude identifies every compliance risk, and watches are auto-created. The frontend already has `CommandBar` with a placeholder button — wire it up.

### Backend: `backend/app/services/onboarding_service.py` (new file)

Three stages:

**Stage 1 — Scrape product page:**
One BrowserUse task. Extract product description, feature list, data handling practices, any compliance mentions.

```python
async def scrape_product_page(url: str) -> str:
    from browser_use import Agent, Browser, ChatBrowserUse
    browser = Browser(headless=True, use_cloud=bool(config.get("browser_use_api_key")))
    agent = Agent(
        task=f"""Go to {url}.
Extract comprehensively:
1. What the product does (core functionality)
2. What user data it collects or processes
3. Who the target customers are (B2B, B2C, healthcare, finance, etc.)
4. Any integrations or third-party services mentioned
5. Any existing compliance mentions (GDPR, HIPAA, SOC2, etc.)

Use the save_content action with everything you find.""",
        llm=ChatBrowserUse(),
        browser=browser,
    )
    history = await agent.run()
    return history.final_result() or ""
```

**Stage 2 — Claude risk analysis:**

```python
async def analyze_compliance_risks(product_description: str) -> list[dict]:
    client = Anthropic(api_key=config["anthropic_api_key"])
    response = client.messages.create(
        model=config.get("claude_model", "claude-sonnet-4-20250514"),
        max_tokens=8192,
        system="""You are a world-class compliance attorney specializing in regulatory technology.
You identify microscopic compliance risks — not just the obvious ones that every company knows about,
but the specific, nuanced regulatory exposures based on exactly what the product does.
Return only valid JSON, no markdown.""",
        messages=[{"role": "user", "content": f"""Analyze this product for ALL compliance risks.

Product description:
{product_description}

For each risk, return a JSON object:
{{
  "regulation_title": "GDPR Article 22 – Automated Decision-Making",
  "why_its_a_risk": "The product uses ML to automatically approve/reject users without human review, triggering Article 22 rights.",
  "jurisdiction": "EU",
  "source_type": "regulator",
  "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
  "current_state": "Article 22 prohibits solely automated decisions that significantly affect individuals, with exceptions for contract necessity, explicit consent, or EU/Member State law.",
  "impact_level": "high",
  "check_interval": 604800,
  "targets": [{{
    "name": "GDPR Article 22",
    "starting_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
    "extraction_instructions": "Extract the full text of Article 22 and any recitals referencing automated decision-making."
  }}]
}}

Return a JSON array of all risks. Be thorough — find 10-20 risks including vendor obligations, state-level laws, sector-specific regulations, and international requirements."""}],
    )
    text = response.content[0].text
    return json.loads(text)  # parse the array
```

**Stage 3 — Bulk watch creation + bootstrap snapshots:**

```python
async def create_watches_from_risks(risks: list[dict], org_id: str) -> list[dict]:
    created = []
    for risk in risks:
        watch = await watch_service.create_watch(
            organization_id=org_id,
            name=risk["regulation_title"],
            description=risk["why_its_a_risk"],
            config={
                "jurisdictions": [risk["jurisdiction"]],
                "sources": [risk.get("source_url", "")],
                "source_type": risk["source_type"],
                "targets": risk.get("targets", []),
                "initial_state": risk.get("current_state"),  # bootstrap; written as first snapshot
            },
        )
        # Write initial snapshot so first real run can diff against it
        if risk.get("current_state"):
            import hashlib
            content = risk["current_state"]
            await watch_service.save_snapshot(
                watch_id=str(watch["id"]),
                run_id="bootstrap",
                target_name=risk["regulation_title"],
                url=risk.get("source_url", ""),
                content_text=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
            )
        created.append(watch)
    return created
```

**Routes:**

```python
import uuid

_onboard_jobs: dict = {}  # in-memory for hackathon; use Redis/Supabase in prod

@router.post("/onboard")
async def onboard_product(body: dict, background_tasks: BackgroundTasks):
    product_url = body.get("product_url")
    if not product_url:
        raise HTTPException(400, "product_url required")
    job_id = str(uuid.uuid4())
    _onboard_jobs[job_id] = {"status": "processing", "stage": "scraping"}
    background_tasks.add_task(_run_onboarding, job_id, product_url)
    return {"job_id": job_id, "status": "processing"}

@router.get("/onboard/{job_id}")
async def get_onboard_status(job_id: str):
    job = _onboard_jobs.get(job_id)
    if not job:
        raise HTTPException(404)
    return job

async def _run_onboarding(job_id: str, product_url: str):
    try:
        _onboard_jobs[job_id]["stage"] = "scraping"
        description = await scrape_product_page(product_url)

        _onboard_jobs[job_id]["stage"] = "analyzing"
        risks = await analyze_compliance_risks(description)
        _onboard_jobs[job_id]["risks"] = risks  # frontend can show preview

        _onboard_jobs[job_id]["stage"] = "creating_watches"
        watches = await create_watches_from_risks(risks, DEFAULT_ORG_ID)

        _onboard_jobs[job_id] = {
            "status": "completed",
            "stage": "done",
            "risks": risks,
            "watches_created": [serialize_watch(w) for w in watches],
        }
    except Exception as e:
        _onboard_jobs[job_id] = {"status": "failed", "error": str(e)}
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

Loading state (poll `GET /api/onboard/{job_id}` every 2s):
```
┌─────────────────────────────────────────────────────┐
│  Analyzing yourapp.com...                            │
│                                                      │
│  ✓ Scraping product page                            │
│  ⟳ Identifying regulations...    (14 found so far)  │
│  ○ Creating watches                                  │
└─────────────────────────────────────────────────────┘
```

Review state (before committing):
```
┌─────────────────────────────────────────────────────┐
│  14 compliance risks identified                      │
│                                                      │
│  ● HIGH   GDPR Article 22 – Auto Decisions    [EU]  │
│  ● HIGH   HIPAA PHI Tracking                  [US]  │
│  ● MED    CCPA Right-to-Delete                [US-CA]│
│  ● MED    Stripe Acceptable Use               [US]  │
│  ● LOW    WCAG 2.1 Accessibility              [US]  │
│  ...                                                 │
│                                                      │
│  [Create all 14 watches]    [Cancel]                 │
└─────────────────────────────────────────────────────┘
```

On "Create all 14 watches": call `api.watches.create()` for each (they're already created by the backend, so just `mutate("watches")` to refresh the list). Or the backend creates them immediately; the frontend just navigates to `/watches`.

---

## 10. Implementation Order

Each phase is independently deployable and testable.

### Phase 1 — Backend serializers (3-4 hours)
1. Create `backend/app/serializers.py` with all serializers above
2. Run DB migration: add `agent_summary`, `agent_thoughts` columns from ai-shit branch
3. Update `_watch_to_response` in routes.py to call `serialize_watch()`
4. Test `GET /api/watches` returns `Watch[]` shape exactly
5. Add `GET /api/globe-points` → `serialize_globe_points()`

### Phase 2 — New read endpoints (2-3 hours)
6. Add `GET /api/changes` → `ChangeEvent[]` shape
7. Add `GET /api/watches/{id}/changes`
8. Add `GET /api/watches/{id}/runs` → lean `Run[]`
9. Update `GET /api/runs/{id}` to fetch changes+evidence and return full `Run` shape
10. Update `GET /api/runs/recent` to return lean `Run[]`

### Phase 3 — Frontend wiring, read-only (2-3 hours)
11. Add `frontend/.env.local` + install `swr`
12. Create `src/lib/api.ts`
13. Wire `/watches` page — replace mock, verify real data renders
14. Wire `/watches/[id]` page
15. Wire `/history` page
16. Wire `/app` dashboard (watches card, changes card, globe)

### Phase 4 — Run detail (2 hours)
17. Wire `/app/run/[id]` — replace `getRunById` with `useSWR`
18. Add loading state for when run is `null`
19. Verify `RunTimeline`, `DiffViewer`, `EvidenceBundle` all render correctly with real data

### Phase 5 — Live run triggering (2-3 hours)
20. DB migration: add `run_steps_log` column to `watch_runs`
21. Add step-writing to orchestrator `spawn_handler`
22. Update `POST /api/watches/{id}/run` to return `run_id`
23. Replace fake animation in Dashboard `runAll` with real poll loop
24. Add "Run now" button wiring on `/watches/[id]`

### Phase 6 — Onboarding (1 day)
25. Create `backend/app/services/onboarding_service.py`
26. Add `POST /api/onboard` + `GET /api/onboard/{job_id}` routes
27. Add onboarding modal component to frontend
28. Wire `CommandBar` "Analyze product" button to open modal

### Phase 7 — Polish + SSE (optional, ½ day)
29. Replace poll with SSE stream endpoint
30. Add `useRunStream` hook
31. Handle error states (run failed, watch not found, API down)
