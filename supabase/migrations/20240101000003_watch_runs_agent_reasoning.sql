-- Store browser-use agent reasoning per run (AGENTS_BROWSERUSE: history.model_thoughts())
ALTER TABLE watch_runs
  ADD COLUMN IF NOT EXISTS agent_summary TEXT,
  ADD COLUMN IF NOT EXISTS agent_thoughts JSONB;

COMMENT ON COLUMN watch_runs.agent_summary IS 'Short summary of agent reasoning for list view';
COMMENT ON COLUMN watch_runs.agent_thoughts IS 'Full agent reasoning from model_thoughts() per task';
