-- Real-time per-step log for live frontend polling
ALTER TABLE watch_runs
  ADD COLUMN IF NOT EXISTS run_steps_log JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN watch_runs.run_steps_log IS 'Ordered list of RunStep objects written during execution for SSE/polling';
