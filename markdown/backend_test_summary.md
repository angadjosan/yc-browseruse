# Backend Test & Fix Summary

## Test Results: 16/16 Endpoints Passing

All endpoints tested with `curl` against the live backend at `http://127.0.0.1:8000`.

| # | Method | Endpoint | Status |
|---|--------|----------|--------|
| 1 | GET | `/` | 200 |
| 2 | GET | `/api/health` | 200 |
| 3 | GET | `/api/watches` | 200 |
| 4 | GET | `/api/watches/{id}` | 200 |
| 5 | GET | `/api/watches/nonexistent` | 404 |
| 6 | GET | `/api/watches/{id}/history` | 200 |
| 7 | GET | `/api/runs/recent` | 200 |
| 8 | GET | `/api/runs/{id}` | 200 |
| 9 | GET | `/api/evidence` | 200 |
| 10 | GET | `/api/evidence/nonexistent` | 404 |
| 11 | POST | `/api/watches` | 200 |
| 12 | POST | `/api/watches/{id}/run` | 200 (queued) |
| 13 | POST | `/api/watches/nonexistent/run` | 404 |
| 14 | POST | `/api/analyze-product` | 200 (queued instantly) |
| 15 | GET | `/api/analyze-product/{job_id}` | 200 |
| 16 | GET | `/api/analyze-product/nonexistent` | 404 |

Concurrent request benchmark: all 5 endpoints responded in **<50ms total**.

---

## Bugs Fixed

### 1. `max_steps` in wrong place (browser-use 0.12.0 API change)

**Files:** `backend/app/services/orchestrator.py`, `backend/app/services/product_analyzer.py`

In browser-use 0.12.0, `max_steps` moved from the `Agent()` constructor to `agent.run()`. The old code passed it to the constructor where it was silently swallowed by `**kwargs`, causing agents to run with the default 500-step limit.

```python
# Before
agent = Agent(task=..., llm=..., max_steps=30)
history = await agent.run()

# After
agent = Agent(task=..., llm=...)
history = await agent.run(max_steps=30)
```

### 2. `POST /api/analyze-product` blocked the HTTP connection

**File:** `backend/app/api/routes.py`

The endpoint was synchronously awaiting the full workflow (browser-use scrapes product page + Claude generates 10-20 risks + browser-use fetches initial state for each regulation). This could take 5-30+ minutes, holding the connection open until completion.

**Fix:** endpoint now returns a `job_id` immediately and runs the analysis as a FastAPI background task.

```
POST /api/analyze-product
→ { "status": "queued", "job_id": "...", "message": "Poll GET /api/analyze-product/{job_id}" }

GET /api/analyze-product/{job_id}
→ { "status": "running" | "completed" | "failed", ... }
```

### 3. Sync Supabase calls blocked the asyncio event loop

**Files:** `backend/app/services/watch_service.py`, `backend/app/services/orchestrator.py`, `backend/app/api/routes.py`

The `supabase-py` client uses synchronous `httpx` under the hood. All `WatchService` methods were declared `async def` but called `.execute()` synchronously, which blocked the event loop for the duration of each Supabase round-trip (~100-500ms on cloud). Under any concurrent load, the server became unresponsive.

**Fix:** all `.execute()` calls wrapped in `asyncio.to_thread()`.

```python
# Before
r = self.db.table("watches").select("*").eq("id", watch_id).execute()

# After
r = await asyncio.to_thread(
    lambda: self.db.table("watches").select("*").eq("id", watch_id).execute()
)
```

---

## `ai_workflow.md` Implementation Status

All three workflow steps described in `ai_workflow.md` are fully implemented:

| Step | Description | Status |
|------|-------------|--------|
| 1 | Browser-use agent scrapes product URL, extracts use cases + features | Implemented in `product_analyzer.py` |
| 2 | Claude generates 10-20 compliance risks with jurisdiction, scope, source URL, `check_interval_seconds`, and initial regulation state snapshot | Implemented in `product_analyzer.py` |
| 3 | A watch is created for every identified risk; `check_interval_seconds` converts to cron schedule; `current_regulation_state` stored at creation time | Implemented in `product_analyzer.py` + `watch_service.py` |
| 4 | Each watch run: Claude agent spawns up to 15 browser-use subagents to scrape regulation pages | Implemented in `orchestrator.py` + `agent_harness.py` |
| 5 | Diff detection: hash + text diff + Claude semantic diff | Implemented in `diff_engine.py` |
| 6 | On change: up to 15 research agents investigate (news, guidance, consulting firms) | Implemented in `orchestrator.py` |
| 7 | Output: new regulation state, exact language diff, how-to-comply summary, change summary | Implemented in `diff_engine.py` + `orchestrator.py` |
| 8 | Linear ticket + Slack message created for every change | Implemented in `notification_hub.py` |
| 9 | Evidence bundle (HMAC-signed, with audit metadata) | Implemented in `evidence_service.py` |
| 10 | APScheduler runs watches per their cron schedule (derived from `check_interval_seconds`) | Implemented in `main.py` |
