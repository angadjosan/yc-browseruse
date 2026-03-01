-- Add diff_summary column to evidence_bundles (used by evidence_service.py)
ALTER TABLE evidence_bundles
  ADD COLUMN IF NOT EXISTS diff_summary TEXT;
