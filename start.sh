#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_DIR="$SCRIPT_DIR/tmp/logs"
mkdir -p "$LOG_DIR"

cleanup() {
  echo ""
  echo "Stopping..."
  for pid in $REDIS_PID $BACKEND_PID $FRONTEND_PID $WORKER_PID; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  exit 0
}
trap cleanup SIGINT SIGTERM

echo "==> Supabase..."
supabase stop --no-backup 2>/dev/null || true
supabase start
supabase db reset || true

echo "==> Redis..."
redis-server >> "$LOG_DIR/redis.log" 2>&1 &
REDIS_PID=$!

echo "==> Frontend (log: $LOG_DIR/frontend.log)..."
(cd "$SCRIPT_DIR/frontend" && npm install --silent && npm run dev) >> "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!

echo "==> Backend (log: $LOG_DIR/backend.log)..."
(
  cd "$SCRIPT_DIR/backend"
  source .venv/bin/activate
  pip install -q -r requirements.txt
  uvicorn app.main:app --reload --port 8000
) >> "$LOG_DIR/backend.log" 2>&1 &
BACKEND_PID=$!

echo "==> Worker (log: $LOG_DIR/worker.log)..."
(
  cd "$SCRIPT_DIR/backend"
  source .venv/bin/activate
  pip install -q -r requirements.txt
  python worker.py
) >> "$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!

echo ""
echo "Logs: $LOG_DIR/"
echo "  tail -f $LOG_DIR/backend.log"
echo "  tail -f $LOG_DIR/frontend.log"
echo "  tail -f $LOG_DIR/worker.log"
echo ""
echo "Backend: http://127.0.0.1:8000  Frontend: http://localhost:3000"
echo "Press Ctrl+C to stop all."
while true; do sleep 60; done
