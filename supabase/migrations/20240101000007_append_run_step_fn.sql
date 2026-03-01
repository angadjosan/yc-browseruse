-- Atomic append to run_steps_log — avoids read-modify-write race when agents run in parallel
CREATE OR REPLACE FUNCTION append_run_step(p_run_id uuid, p_step text)
RETURNS void LANGUAGE sql AS $$
  UPDATE watch_runs
  SET run_steps_log = COALESCE(run_steps_log, '[]'::jsonb) || p_step::jsonb
  WHERE id = p_run_id;
$$;
