# Setup and Run Instructions

## ✅ API Keys Verification

Your `.env` file is correctly configured with all necessary API keys:

```
✓ SUPABASE_URL
✓ SUPABASE_SERVICE_ROLE_KEY
✓ ANTHROPIC_API_KEY
✓ BROWSER_USE_API_KEY
✓ LINEAR_API_KEY
✓ SLACK_BOT_TOKEN
✓ SLACK_SIGNING_SECRET
✓ REDIS_URL
✓ CLAUDE_MODEL (set to claude-sonnet-4-6)
```

All keys in `app/config.py` match the `.env` file. ✅

---

## Prerequisites

Make sure you have the following installed:

1. **Python 3.13+** (you have 3.13.3 ✅)
2. **Node.js 18+** (for frontend)
3. **Supabase CLI** - [Install guide](https://supabase.com/docs/guides/cli/getting-started)
4. **Redis** - [Install guide](https://redis.io/docs/getting-started/installation/)
5. **Docker Desktop** (required for Supabase local development)

### Install Supabase CLI (if not installed)

```bash
# macOS
brew install supabase/tap/supabase

# Verify installation
supabase --version
```

### Install Redis (if not installed)

```bash
# macOS
brew install redis

# Verify installation
redis-server --version
```

---

## Quick Start (Automated)

The easiest way to run everything:

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse

# Make sure start.sh is executable
chmod +x start.sh

# Run the start script
./start.sh
```

This script will:
1. Stop any existing Supabase instance
2. Start Supabase (with Docker)
3. Reset the database (run all migrations including the new regulation fields)
4. Start Redis
5. Create Python virtual environment and install dependencies
6. Start backend (FastAPI with auto-reload)
7. Start frontend (Next.js with auto-reload)

**Logs are saved to:** `tmp/logs/`
- Backend: `tail -f tmp/logs/backend.log`
- Frontend: `tail -f tmp/logs/frontend.log`
- Redis: `tail -f tmp/logs/redis.log`

Press **Ctrl+C** to stop all services.

---

## Manual Setup (Step by Step)

If you prefer to set up manually or if the automated script has issues:

### 1. Setup Backend

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse/backend

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Setup Database (Supabase)

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse

# Start Supabase (requires Docker Desktop running)
supabase start

# Apply all migrations (including new regulation fields)
supabase db reset

# Check Supabase status
supabase status
```

**Important URLs from `supabase status`:**
- API URL: `http://127.0.0.1:54321`
- DB URL: `postgresql://postgres:postgres@localhost:54322/postgres`
- Studio URL: `http://127.0.0.1:54323` (Database UI)

### 3. Start Redis

```bash
# Start Redis server
redis-server
```

Or if you want it in the background:

```bash
redis-server --daemonize yes
```

### 4. Start Backend

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse/backend

# Make sure virtual environment is activated
source .venv/bin/activate

# Start FastAPI server with auto-reload
uvicorn app.main:app --reload --port 8000
```

Backend will be available at: **http://127.0.0.1:8000**
API docs: **http://127.0.0.1:8000/docs**

### 5. Start Frontend (Optional)

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse/frontend

# Install dependencies (first time only)
npm install

# Start development server
npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## Testing the New AI Workflow

### 1. Test Product Analysis Endpoint

```bash
curl -X POST http://127.0.0.1:8000/api/analyze-product \
  -H "Content-Type: application/json" \
  -d '{
    "product_url": "https://example.com/your-product-page"
  }'
```

This will:
1. Use browser-use to extract product info
2. Use Claude to identify 10-20+ compliance risks
3. Create watches for each risk
4. Return the list of created watches

**Example product URLs to test:**
- A SaaS product landing page
- A fintech product page
- A healthcare tech product page

### 2. View Created Watches

```bash
# List all watches
curl http://127.0.0.1:8000/api/watches
```

### 3. Manually Trigger a Watch

```bash
# Replace WATCH_ID with actual watch ID from above
curl -X POST http://127.0.0.1:8000/api/watches/WATCH_ID/run
```

This will:
1. Extract current regulation state using browser-use
2. Compare with previous state
3. If change detected, spawn up to 15 research agents
4. Generate compliance and change summaries
5. Send Linear ticket and Slack notification

### 4. View Watch History

```bash
curl http://127.0.0.1:8000/api/watches/WATCH_ID/history
```

### 5. View Recent Runs

```bash
curl http://127.0.0.1:8000/api/runs/recent?limit=10
```

---

## API Endpoints Reference

### New Endpoint (Product Analysis)

- **POST** `/api/analyze-product` - Analyze product URL and create compliance watches
  - Request body: `{"product_url": "https://..."}`
  - Returns: list of created watches with risk details

### Existing Endpoints

- **GET** `/api/watches` - List all watches
- **POST** `/api/watches` - Create watch manually
- **GET** `/api/watches/{watch_id}` - Get watch details
- **POST** `/api/watches/{watch_id}/run` - Trigger watch execution
- **GET** `/api/watches/{watch_id}/history` - Get watch run history
- **GET** `/api/runs/recent` - Recent runs across all watches
- **GET** `/api/runs/{run_id}` - Get specific run details
- **GET** `/api/evidence` - List evidence bundles
- **GET** `/api/health` - Health check

Full API docs: **http://127.0.0.1:8000/docs**

---

## Database Management

### View Database in Supabase Studio

```bash
# Open Supabase Studio (web UI)
open http://127.0.0.1:54323
```

Or check the URL from:
```bash
supabase status
```

### Connect with psql

```bash
psql postgresql://postgres:postgres@localhost:54322/postgres
```

### View Watch Data

```sql
-- View all watches with regulation details
SELECT id, name, regulation_title, jurisdiction, check_interval_seconds
FROM watches
ORDER BY created_at DESC;

-- View watches with current regulation state
SELECT id, name, regulation_title,
       LEFT(current_regulation_state, 100) as state_preview
FROM watches
WHERE current_regulation_state IS NOT NULL;

-- View recent changes with summaries
SELECT c.id, w.name, c.impact_level, c.diff_summary,
       c.diff_details->>'compliance_summary' as compliance,
       c.diff_details->>'change_summary' as change_detail
FROM changes c
JOIN watches w ON c.watch_id = w.id
ORDER BY c.detected_at DESC
LIMIT 10;
```

---

## Troubleshooting

### Issue: "Docker not running"

**Solution:** Start Docker Desktop before running `supabase start`.

### Issue: "Port already in use"

**Solution:** Stop existing services:

```bash
# Stop Supabase
supabase stop

# Kill processes on specific ports
lsof -ti:8000 | xargs kill -9  # Backend
lsof -ti:3000 | xargs kill -9  # Frontend
lsof -ti:6379 | xargs kill -9  # Redis
```

### Issue: "Module not found" errors

**Solution:** Reinstall Python dependencies:

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse/backend
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: "browser-use API key invalid"

**Solution:** Check your Browser Use API key:
1. Visit https://browseruse.com
2. Get a valid API key
3. Update `BROWSER_USE_API_KEY` in `.env`

### Issue: "Anthropic API key invalid"

**Solution:** Check your Anthropic API key:
1. Visit https://console.anthropic.com
2. Get a valid API key
3. Update `ANTHROPIC_API_KEY` in `.env`

### Issue: Database migration fails

**Solution:** Reset Supabase:

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse
supabase db reset --no-backup
```

---

## Monitoring and Logs

### Backend Logs

```bash
# If using start.sh
tail -f tmp/logs/backend.log

# If running manually
# Logs appear in terminal where uvicorn is running
```

### Watch for Specific Events

```bash
# Watch for product analysis
tail -f tmp/logs/backend.log | grep "product analysis"

# Watch for research agents
tail -f tmp/logs/backend.log | grep "research agent"

# Watch for change detection
tail -f tmp/logs/backend.log | grep "Change detected"
```

### Database Logs

```bash
# View Supabase logs
supabase logs
```

---

## Development Workflow

### Making Code Changes

The backend automatically reloads when you edit Python files (with `--reload` flag).

### Testing Changes

1. Edit backend code in `/backend/app/`
2. Backend auto-reloads
3. Test via API: http://127.0.0.1:8000/docs
4. Check logs: `tail -f tmp/logs/backend.log`

### Adding New Dependencies

```bash
cd /Users/potthi/Desktop/Projects/yc-browseruse/backend
source .venv/bin/activate
pip install <package-name>
pip freeze > requirements.txt
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] Update all API keys in production environment
- [ ] Change `EVIDENCE_SIGNING_KEY` to a secure random value
- [ ] Set up production Supabase instance
- [ ] Set up production Redis instance
- [ ] Configure proper CORS origins in `backend/app/main.py`
- [ ] Enable RLS policies in Supabase
- [ ] Set up monitoring and error tracking
- [ ] Configure proper Linear and Slack integrations
- [ ] Test with real product URLs
- [ ] Set up SSL/TLS certificates
- [ ] Configure proper logging and log rotation

---

## Support and Documentation

- **API Documentation**: http://127.0.0.1:8000/docs
- **Implementation Details**: See `backend/IMPLEMENTATION_SUMMARY.md`
- **AI Workflow Spec**: See `markdown/ai_workflow.md`
- **Database Schema**: See `supabase/migrations/`

---

## Quick Reference

```bash
# Start everything (easiest)
./start.sh

# Stop everything
Ctrl+C

# Restart Supabase
supabase stop && supabase start

# Reset database
supabase db reset

# View Supabase status
supabase status

# Activate Python environment
cd backend && source .venv/bin/activate

# Run tests (if available)
cd backend && pytest

# View logs
tail -f tmp/logs/backend.log
tail -f tmp/logs/frontend.log
```

---

## Next Steps

1. **Run the application**: `./start.sh`
2. **Test product analysis**: POST to `/api/analyze-product` with a product URL
3. **View API docs**: Visit http://127.0.0.1:8000/docs
4. **Check database**: Visit http://127.0.0.1:54323 (Supabase Studio)
5. **Monitor logs**: `tail -f tmp/logs/backend.log`

Enjoy monitoring compliance changes! 🚀
