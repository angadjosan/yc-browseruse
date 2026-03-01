#!/usr/bin/env bash
# Start full local dev stack: Supabase, Redis, backend (reload), frontend (reload).
# Logs go to tmp/logs/ — e.g. tail -f tmp/logs/backend.log

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/tmp/logs"
mkdir -p "$LOG_DIR"

echo "==> Stopping any existing Supabase (ignore errors)..."
supabase stop --no-backup 2>/dev/null || true

echo "==> Starting Supabase..."
supabase start

echo "==> Resetting database (migrations + seed)..."
supabase db reset

echo "==> Starting Redis, backend, frontend (logs in $LOG_DIR)..."
REDIS_PID=""
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  echo ""
  echo "==> Shutting down..."
  for name in FRONTEND BACKEND REDIS; do
    pid_var="${name}_PID"
    pid="${!pid_var}"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

# Redis (foreground in background, with log)
redis-server >> "$LOG_DIR/redis.log" 2>&1 &
REDIS_PID=$!

# Backend with reload (pip install -q so first run has deps)
(
  cd "$SCRIPT_DIR/backend" && \
  source .venv/bin/activate && \
  pip install -q -r requirements.txt && \
  uvicorn app.main:app --reload --port 8000
) >> "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

# Frontend with dev (reload)
(
  cd "$SCRIPT_DIR/frontend" && \
  npm run dev
) >> "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "Services started. Logs:"
echo "  backend  tail -f $LOG_DIR/backend.log"
echo "  frontend tail -f $LOG_DIR/frontend.log"
echo "  redis    tail -f $LOG_DIR/redis.log"
echo ""
echo "Backend:  http://127.0.0.1:8000"
echo "Frontend: http://localhost:3000"
echo "Supabase: run 'supabase status' for URLs"
echo ""
echo "Press Ctrl+C to stop all."
wait $REDIS_PID $BACKEND_PID $FRONTEND_PID
