-- Enable Realtime for live updates
ALTER PUBLICATION supabase_realtime ADD TABLE watches;
ALTER PUBLICATION supabase_realtime ADD TABLE watch_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE changes;

-- Create function for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at (Postgres 11+ EXECUTE FUNCTION)
CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_watches_updated_at
    BEFORE UPDATE ON watches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integrations_updated_at
    BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
