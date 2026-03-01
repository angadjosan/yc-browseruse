# Compliance Change Radar

Describe your product; we automatically watch every regulation and vendor policy that affects you, and ticket your team the second something changes.

- **Backend:** FastAPI (Python), Supabase (Postgres + Auth + Storage), Claude (orchestrator), Browser-Use (automation), Linear + Slack (notifications).
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind — black/green SaaS theme.

## Quick start

### 1. Environment

Copy `.env.example` to `.env` and fill in keys (see [API keys](#api-keys)). Never commit `.env` (it’s gitignored).

```bash
cp .env.example .env
```

### 2. Supabase (database)

```bash
# Install Supabase CLI (macOS)
brew install supabase/tap/supabase

# Start local Supabase (Postgres, Auth, Realtime, Storage)
supabase start
```

After `supabase start`, copy the printed **API URL**, **anon key**, and **service_role key** into `.env`:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

(Optional) For the frontend, create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=<from supabase start>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from supabase start>
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://localhost:3000

## API keys

Add these to the project root `.env` (or backend `.env`). Backend reads them at runtime.

| Variable | Purpose |
|----------|--------|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | Database and storage (required for backend). |
| `ANTHROPIC_API_KEY` | Claude — orchestrator plans and semantic diff. |
| `CLAUDE_MODEL` | Claude model name (e.g. `claude-sonnet-4-20250514`). Optional; has a default. |
| `BROWSER_USE_API_KEY` | Browser-Use — real browser automation. Without this, runs use mock data. |
| `LINEAR_API_KEY` | Create Linear issues when a change is detected. |
| `SLACK_BOT_TOKEN` | Send Slack notifications. |
| `EVIDENCE_SIGNING_KEY` | HMAC signing for evidence integrity (use a random secret). |

Frontend only needs `NEXT_PUBLIC_API_URL` (and optionally Supabase keys if you add auth later).

## Project layout

- `backend/` — FastAPI app, Supabase client, orchestrator, diff/evidence/notification services.
- `frontend/` — Next.js app: Dashboard, Watches (list/create/detail + run), History, Evidence viewer, Settings.
- `supabase/` — Config, migrations, seed. Run with `supabase start`.

## Product summary (from compliance.md)

- You provide a product description and/or explicit watch list.
- Each **watch** has targets (e.g. “GDPR Article 25”, “Vendor X ToS”) and a schedule.
- The **orchestrator** (Claude) assigns tasks to **browser-use** agents, which search and navigate multi-step flows, capture text + screenshot + hash.
- On each run, we **diff** against the previous snapshot; on change we generate an **evidence bundle** (impact memo, diff, screenshots, hash) and **notify** (Linear ticket, Slack).
- Retries and self-healing at the orchestrator level keep runs reliable.

## License

Private / as per your repo.
