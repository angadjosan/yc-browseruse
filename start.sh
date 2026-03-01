#!/usr/bin/env bash
# Start full local dev stack: Supabase, Redis, backend (reload), frontend (reload).
# Logs go to tmp/logs/ — e.g. tail -f tmp/logs/backend.log

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/tmp/logs"
mkdir -p "$LOG_DIR"

VENV="$SCRIPT_DIR/backend/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"
UVICORN="$VENV/bin/uvicorn"

# ── Supabase ────────────────────────────────────────────────────────────────
echo "==> Stopping any existing Supabase (ignore errors)..."
supabase stop --no-backup 2>/dev/null || true

echo "==> Starting Supabase..."
if ! supabase start; then
  echo "ERROR: supabase start failed. Is Docker Desktop running?"
  exit 1
fi

echo "==> Resetting database (migrations + seed)..."
supabase db reset || echo "WARNING: db reset failed, continuing..."

# ── Python venv ─────────────────────────────────────────────────────────────
echo "==> Setting up Python virtual environment..."
if [[ ! -f "$VENV/bin/activate" ]]; then
  echo "    Creating venv at $VENV ..."
  python3 -m venv "$VENV"
fi

echo "==> Installing Python dependencies..."
"$PIP" install -q --upgrade pip
"$PIP" install -q -r "$SCRIPT_DIR/backend/requirements.txt"

# ── Frontend deps ────────────────────────────────────────────────────────────
echo "==> Setting up frontend..."
if [[ ! -d "$SCRIPT_DIR/frontend/node_modules" ]]; then
  echo "    Installing npm dependencies..."
  cd "$SCRIPT_DIR/frontend" && npm install --legacy-peer-deps
  cd "$SCRIPT_DIR"
fi

# ── Start services ───────────────────────────────────────────────────────────
echo "==> Starting Redis, backend, frontend (logs in $LOG_DIR)..."

REDIS_PID=""
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "==> Shutting down..."
  for pid in "$FRONTEND_PID" "$BACKEND_PID" "$REDIS_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

# Redis
redis-server >> "$LOG_DIR/redis.log" 2>&1 &
REDIS_PID=$!

# Backend
(
  cd "$SCRIPT_DIR/backend"
  "$UVICORN" app.main:app --reload --port 8000
) >> "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Frontend
(
  cd "$SCRIPT_DIR/frontend"
  npm run dev
) >> "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "Services started. Logs:"
echo "  backend  →  tail -f $LOG_DIR/backend.log"
echo "  frontend →  tail -f $LOG_DIR/frontend.log"
echo "  redis    →  tail -f $LOG_DIR/redis.log"
echo ""
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://localhost:3000"
echo "Supabase: run 'supabase status' for URLs"
echo ""
echo "Press Ctrl+C to stop all."
wait $REDIS_PID $BACKEND_PID $FRONTEND_PID
