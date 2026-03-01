-- Store Linear (or Jira) ticket URL and title on evidence_bundles for run detail display
ALTER TABLE evidence_bundles
  ADD COLUMN IF NOT EXISTS linear_ticket_url TEXT,
  ADD COLUMN IF NOT EXISTS ticket_title TEXT;
