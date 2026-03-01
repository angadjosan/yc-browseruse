-- Add regulation-specific fields to watches table
-- These fields support the AI workflow for product analysis and risk monitoring

ALTER TABLE watches
ADD COLUMN IF NOT EXISTS regulation_title TEXT,
ADD COLUMN IF NOT EXISTS risk_rationale TEXT,
ADD COLUMN IF NOT EXISTS jurisdiction TEXT,
ADD COLUMN IF NOT EXISTS scope TEXT,
ADD COLUMN IF NOT EXISTS source_url TEXT,
ADD COLUMN IF NOT EXISTS check_interval_seconds INTEGER,
ADD COLUMN IF NOT EXISTS current_regulation_state TEXT;

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_watches_regulation_title ON watches(regulation_title);
CREATE INDEX IF NOT EXISTS idx_watches_jurisdiction ON watches(jurisdiction);
CREATE INDEX IF NOT EXISTS idx_watches_check_interval ON watches(check_interval_seconds);

-- Add comment for documentation
COMMENT ON COLUMN watches.regulation_title IS 'Official title of the regulation being monitored';
COMMENT ON COLUMN watches.risk_rationale IS 'Explanation of why this regulation applies to the product';
COMMENT ON COLUMN watches.jurisdiction IS 'Geographic scope (e.g., EU, California, United States)';
COMMENT ON COLUMN watches.scope IS 'Which aspects of the product are affected';
COMMENT ON COLUMN watches.source_url IS 'Official URL to the regulation text';
COMMENT ON COLUMN watches.check_interval_seconds IS 'How often to check this regulation (in seconds)';
COMMENT ON COLUMN watches.current_regulation_state IS 'Current text/state of the regulation, updated on each run';
