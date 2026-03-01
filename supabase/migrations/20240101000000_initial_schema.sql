-- Organizations table (gen_random_uuid() is built-in in PostgreSQL 13+)
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    product_description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Users table (Supabase Auth integration)
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'viewer', -- admin, analyst, viewer
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);

-- Watches table
CREATE TABLE watches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    schedule JSONB NOT NULL,
    integrations JSONB,
    status VARCHAR(50) DEFAULT 'active', -- active, paused, archived
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ
);

-- Indexes for watches
CREATE INDEX idx_watches_org ON watches(organization_id);
CREATE INDEX idx_watches_status ON watches(status);
CREATE INDEX idx_watches_next_run ON watches(next_run_at) WHERE status = 'active';

-- Watch runs table
CREATE TABLE watch_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- running, completed, failed, partial
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    tasks_executed INTEGER DEFAULT 0,
    tasks_failed INTEGER DEFAULT 0,
    changes_detected INTEGER DEFAULT 0,
    error_message TEXT
);

-- Indexes for watch_runs
CREATE INDEX idx_runs_watch ON watch_runs(watch_id);
CREATE INDEX idx_runs_started ON watch_runs(started_at DESC);
CREATE INDEX idx_runs_status ON watch_runs(status);

-- Snapshots table (captured content per target per run)
CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id) ON DELETE CASCADE,
    target_name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    content_text TEXT,
    content_html TEXT,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256
    screenshot_url TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

-- Indexes for snapshots
CREATE INDEX idx_snapshots_watch ON snapshots(watch_id);
CREATE INDEX idx_snapshots_run ON snapshots(run_id);
CREATE INDEX idx_snapshots_target ON snapshots(watch_id, target_name);
CREATE INDEX idx_snapshots_hash ON snapshots(content_hash);

-- Changes table (detected diffs)
CREATE TABLE changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id) ON DELETE CASCADE,
    target_name VARCHAR(255) NOT NULL,
    previous_snapshot_id UUID REFERENCES snapshots(id),
    current_snapshot_id UUID REFERENCES snapshots(id),
    diff_summary TEXT,
    diff_details JSONB,
    impact_level VARCHAR(20), -- low, medium, high, critical
    detected_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for changes
CREATE INDEX idx_changes_watch ON changes(watch_id);
CREATE INDEX idx_changes_detected ON changes(detected_at DESC);
CREATE INDEX idx_changes_impact ON changes(impact_level);

-- Evidence bundles table
CREATE TABLE evidence_bundles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id UUID REFERENCES changes(id) ON DELETE CASCADE,
    run_id UUID REFERENCES watch_runs(id),
    impact_memo TEXT,
    diff_url TEXT,
    screenshots JSONB,
    content_hash VARCHAR(64),
    audit_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for evidence_bundles
CREATE INDEX idx_evidence_change ON evidence_bundles(change_id);
CREATE INDEX idx_evidence_created ON evidence_bundles(created_at DESC);

-- Notifications table (audit trail)
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id UUID REFERENCES changes(id) ON DELETE CASCADE,
    evidence_bundle_id UUID REFERENCES evidence_bundles(id),
    channel VARCHAR(50), -- linear, slack, email
    status VARCHAR(50), -- sent, failed, pending
    external_id VARCHAR(255),
    external_url TEXT,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    error_message TEXT
);

-- Indexes for notifications
CREATE INDEX idx_notifications_change ON notifications(change_id);
CREATE INDEX idx_notifications_status ON notifications(status);

-- Integrations table
CREATE TABLE integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
    service VARCHAR(50), -- linear, slack, jira
    config JSONB, -- encrypted API keys, team IDs, channels
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for integrations
CREATE INDEX idx_integrations_org ON integrations(organization_id);

-- Enable Row Level Security (RLS)
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watches ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_bundles ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

-- RLS Policies (users can only access data from their organization)
CREATE POLICY "Users can view their organization"
    ON organizations FOR SELECT
    USING (id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can view users in their organization"
    ON users FOR SELECT
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can view their organization's watches"
    ON watches FOR ALL
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));

CREATE POLICY "Users can view their organization's runs"
    ON watch_runs FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));

CREATE POLICY "Users can view their organization's snapshots"
    ON snapshots FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));

CREATE POLICY "Users can view their organization's changes"
    ON changes FOR SELECT
    USING (watch_id IN (
        SELECT id FROM watches WHERE organization_id IN (
            SELECT organization_id FROM users WHERE id = auth.uid()
        )
    ));

CREATE POLICY "Users can view their organization's evidence bundles"
    ON evidence_bundles FOR SELECT
    USING (change_id IN (
        SELECT id FROM changes WHERE watch_id IN (
            SELECT id FROM watches WHERE organization_id IN (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    ));

CREATE POLICY "Users can view their organization's notifications"
    ON notifications FOR SELECT
    USING (change_id IN (
        SELECT id FROM changes WHERE watch_id IN (
            SELECT id FROM watches WHERE organization_id IN (
                SELECT organization_id FROM users WHERE id = auth.uid()
            )
        )
    ));

CREATE POLICY "Users can view their organization's integrations"
    ON integrations FOR SELECT
    USING (organization_id IN (
        SELECT organization_id FROM users WHERE id = auth.uid()
    ));
