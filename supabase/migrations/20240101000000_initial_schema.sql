-- Compliance Change Radar — Consolidated Schema
-- All tables, indexes, RLS policies, functions, triggers, realtime, storage

-- ═══════════════════════════════════════════════════════════════════════════
-- ENUMS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TYPE watch_status AS ENUM ('active', 'paused', 'archived');
CREATE TYPE run_status AS ENUM ('pending', 'running', 'completed', 'failed', 'partial');
CREATE TYPE impact_level AS ENUM ('low', 'medium', 'high', 'critical');
CREATE TYPE user_role AS ENUM ('owner', 'admin', 'analyst', 'viewer');
CREATE TYPE notification_channel AS ENUM ('linear', 'email');
CREATE TYPE notification_status AS ENUM ('pending', 'sent', 'failed');
CREATE TYPE integration_service AS ENUM ('linear', 'jira', 'email');

-- ═══════════════════════════════════════════════════════════════════════════
-- ORGANIZATIONS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    slug        VARCHAR(100) UNIQUE,                       -- url-friendly org handle
    product_url TEXT,                                       -- onboarding product URL
    product_description TEXT,
    plan        VARCHAR(50) NOT NULL DEFAULT 'free',       -- free, pro, enterprise
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════
-- USERS (linked to Supabase Auth)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE users (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL,
    name            VARCHAR(255),
    role            user_role NOT NULL DEFAULT 'viewer',
    avatar_url      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login      TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_org ON users(organization_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- API KEYS (org-scoped keys for programmatic access)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    name            VARCHAR(255) NOT NULL,                 -- human label, e.g. "CI pipeline"
    key_hash        VARCHAR(128) NOT NULL,                 -- SHA-256 of the actual key
    key_prefix      VARCHAR(12) NOT NULL,                  -- first 8 chars for identification
    scopes          TEXT[] NOT NULL DEFAULT '{"read"}',    -- read, write, admin
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_api_keys_org ON api_keys(organization_id);
CREATE UNIQUE INDEX idx_api_keys_prefix ON api_keys(key_prefix) WHERE revoked_at IS NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- WATCHES (core monitoring unit)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE watches (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name                     VARCHAR(255) NOT NULL,
    description              TEXT NOT NULL DEFAULT '',

    -- watch type & config
    type                     VARCHAR(50) NOT NULL DEFAULT 'custom',   -- regulation, vendor, internal, custom
    config                   JSONB NOT NULL DEFAULT '{}'::jsonb,      -- targets: [{name, starting_url, search_query, extraction_instructions}]
    schedule                 JSONB NOT NULL DEFAULT '{"cron": "0 9 * * *", "timezone": "UTC"}'::jsonb,
    integrations             JSONB NOT NULL DEFAULT '{}'::jsonb,      -- {linear_team_id, ...}

    -- regulation-specific fields (populated by product analyzer)
    regulation_title         TEXT,
    risk_rationale           TEXT,
    jurisdiction             VARCHAR(100),          -- EU, US-CA, UK, etc.
    scope                    TEXT,                   -- vendor, regulator, internal
    source_url               TEXT,                   -- official regulation URL
    check_interval_seconds   INTEGER,                -- how often to check
    current_regulation_state TEXT,                    -- full text at time of last check

    -- lifecycle
    status                   watch_status NOT NULL DEFAULT 'active',
    created_by               UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_at              TIMESTAMPTZ,
    next_run_at              TIMESTAMPTZ
);

CREATE INDEX idx_watches_org ON watches(organization_id);
CREATE INDEX idx_watches_org_status ON watches(organization_id, status);
CREATE INDEX idx_watches_next_run ON watches(next_run_at) WHERE status = 'active';
CREATE INDEX idx_watches_jurisdiction ON watches(jurisdiction) WHERE jurisdiction IS NOT NULL;

-- ═══════════════════════════════════════════════════════════════════════════
-- WATCH RUNS (execution record per run)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE watch_runs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id          UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    organization_id   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,   -- denormalized for fast tenant queries

    status            run_status NOT NULL DEFAULT 'pending',
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    duration_ms       INTEGER,

    -- task stats
    tasks_executed    INTEGER NOT NULL DEFAULT 0,
    tasks_failed      INTEGER NOT NULL DEFAULT 0,
    changes_detected  INTEGER NOT NULL DEFAULT 0,

    -- agent reasoning (from browser-use)
    agent_summary     TEXT,                             -- short summary for list view
    agent_thoughts    JSONB,                            -- full reasoning per task
    run_steps_log     JSONB NOT NULL DEFAULT '[]'::jsonb,  -- real-time steps [{name, status, timestamp}]

    error_message     TEXT
);

CREATE INDEX idx_runs_watch ON watch_runs(watch_id);
CREATE INDEX idx_runs_org ON watch_runs(organization_id);
CREATE INDEX idx_runs_started ON watch_runs(started_at DESC);
CREATE INDEX idx_runs_status ON watch_runs(status);
CREATE INDEX idx_runs_org_started ON watch_runs(organization_id, started_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════
-- SNAPSHOTS (captured content per target per run)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id        UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    run_id          UUID NOT NULL REFERENCES watch_runs(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,   -- denormalized

    target_name     VARCHAR(255) NOT NULL,
    url             TEXT NOT NULL,
    content_text    TEXT,
    content_html    TEXT,
    content_hash    VARCHAR(64) NOT NULL,      -- SHA-256
    screenshot_url  TEXT,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB
);

CREATE INDEX idx_snapshots_watch ON snapshots(watch_id);
CREATE INDEX idx_snapshots_run ON snapshots(run_id);
CREATE INDEX idx_snapshots_target ON snapshots(watch_id, target_name);
CREATE INDEX idx_snapshots_hash ON snapshots(content_hash);

-- ═══════════════════════════════════════════════════════════════════════════
-- CHANGES (detected diffs)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE changes (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id              UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    run_id                UUID NOT NULL REFERENCES watch_runs(id) ON DELETE CASCADE,
    organization_id       UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,   -- denormalized

    target_name           VARCHAR(255) NOT NULL,
    previous_snapshot_id  UUID REFERENCES snapshots(id) ON DELETE SET NULL,
    current_snapshot_id   UUID REFERENCES snapshots(id) ON DELETE SET NULL,

    diff_summary          TEXT,
    diff_details          JSONB,            -- {text_diff, semantic_diff, compliance_summary, change_summary, research_findings}
    impact_level          impact_level NOT NULL DEFAULT 'medium',

    detected_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_changes_watch ON changes(watch_id);
CREATE INDEX idx_changes_org ON changes(organization_id);
CREATE INDEX idx_changes_detected ON changes(detected_at DESC);
CREATE INDEX idx_changes_impact ON changes(impact_level);
CREATE INDEX idx_changes_org_detected ON changes(organization_id, detected_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════
-- EVIDENCE BUNDLES (audit-ready proof)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE evidence_bundles (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    change_id         UUID NOT NULL REFERENCES changes(id) ON DELETE CASCADE,
    run_id            UUID NOT NULL REFERENCES watch_runs(id) ON DELETE CASCADE,
    organization_id   UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,   -- denormalized

    impact_memo       TEXT,
    diff_summary      TEXT,
    diff_url          TEXT,                  -- URL to signed diff artifact
    screenshots       JSONB,
    content_hash      VARCHAR(64),           -- hash of the bundle itself
    audit_metadata    JSONB,                 -- {run_id, timestamps, hashes, capture_method}

    -- ticket integration
    linear_ticket_url TEXT,
    ticket_title      TEXT,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_change ON evidence_bundles(change_id);
CREATE INDEX idx_evidence_org ON evidence_bundles(organization_id);
CREATE INDEX idx_evidence_created ON evidence_bundles(created_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════
-- NOTIFICATIONS (audit trail)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    change_id           UUID REFERENCES changes(id) ON DELETE CASCADE,
    evidence_bundle_id  UUID REFERENCES evidence_bundles(id) ON DELETE SET NULL,

    channel             notification_channel NOT NULL,
    status              notification_status NOT NULL DEFAULT 'pending',
    external_id         VARCHAR(255),       -- Linear issue ID, etc.
    external_url        TEXT,               -- Linear issue URL, etc.
    error_message       TEXT,

    sent_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_org ON notifications(organization_id);
CREATE INDEX idx_notifications_change ON notifications(change_id);
CREATE INDEX idx_notifications_status ON notifications(status);

-- ═══════════════════════════════════════════════════════════════════════════
-- INTEGRATIONS (service configs per org)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE integrations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    service         integration_service NOT NULL,
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,     -- team IDs, channels, etc. (NO raw API keys here)
    status          VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_integrations_org ON integrations(organization_id);
CREATE UNIQUE INDEX idx_integrations_org_service ON integrations(organization_id, service);

-- ═══════════════════════════════════════════════════════════════════════════
-- AUDIT LOG (track who did what)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    action          VARCHAR(100) NOT NULL,     -- watch.create, watch.run, change.detected, etc.
    resource_type   VARCHAR(50),               -- watch, run, change, evidence
    resource_id     UUID,
    metadata        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_org ON audit_log(organization_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
CREATE INDEX idx_audit_resource ON audit_log(resource_type, resource_id);

-- ═══════════════════════════════════════════════════════════════════════════
-- FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Atomic append to run_steps_log (avoids read-modify-write race)
CREATE OR REPLACE FUNCTION append_run_step(p_run_id UUID, p_step TEXT)
RETURNS void LANGUAGE sql AS $$
  UPDATE watch_runs
  SET run_steps_log = COALESCE(run_steps_log, '[]'::jsonb) || p_step::jsonb
  WHERE id = p_run_id;
$$;

-- Auto-create org + user profile on Supabase Auth signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
    new_org_id UUID;
    user_name TEXT;
BEGIN
    user_name := COALESCE(
        NEW.raw_user_meta_data->>'name',
        NEW.raw_user_meta_data->>'full_name',
        split_part(NEW.email, '@', 1)
    );

    -- Create a personal organization for the user
    INSERT INTO organizations (name, slug)
    VALUES (
        user_name || '''s Organization',
        LOWER(REPLACE(split_part(NEW.email, '@', 1), '.', '-')) || '-' || LEFT(gen_random_uuid()::text, 8)
    )
    RETURNING id INTO new_org_id;

    -- Create the user profile linked to the org
    INSERT INTO users (id, organization_id, email, name, role)
    VALUES (
        NEW.id,
        new_org_id,
        NEW.email,
        user_name,
        'owner'
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger: auto-provision on signup
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- ═══════════════════════════════════════════════════════════════════════════
-- TRIGGERS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TRIGGER update_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_watches_updated_at
    BEFORE UPDATE ON watches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_integrations_updated_at
    BEFORE UPDATE ON integrations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════════════════════════
-- ROW-LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════════════
-- RLS is defense-in-depth. Primary auth is FastAPI JWT middleware.
-- Backend uses service_role key (bypasses RLS). These policies protect
-- against direct Supabase client access.

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE watches ENABLE ROW LEVEL SECURITY;
ALTER TABLE watch_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_bundles ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

-- Helper: get the current user's org_id
CREATE OR REPLACE FUNCTION auth_org_id()
RETURNS UUID LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT organization_id FROM users WHERE id = auth.uid()
$$;

-- Organizations: users see their own org
CREATE POLICY org_select ON organizations FOR SELECT
    USING (id = auth_org_id());

-- Users: see users in same org
CREATE POLICY users_select ON users FOR SELECT
    USING (organization_id = auth_org_id());

-- API keys: org members can manage
CREATE POLICY api_keys_select ON api_keys FOR SELECT
    USING (organization_id = auth_org_id());
CREATE POLICY api_keys_insert ON api_keys FOR INSERT
    WITH CHECK (organization_id = auth_org_id());
CREATE POLICY api_keys_delete ON api_keys FOR DELETE
    USING (organization_id = auth_org_id());

-- Watches: full CRUD scoped to org
CREATE POLICY watches_all ON watches FOR ALL
    USING (organization_id = auth_org_id());

-- Watch runs: read-only for users (workers create via service_role)
CREATE POLICY runs_select ON watch_runs FOR SELECT
    USING (organization_id = auth_org_id());

-- Snapshots: read-only for users
CREATE POLICY snapshots_select ON snapshots FOR SELECT
    USING (organization_id = auth_org_id());

-- Changes: read-only for users
CREATE POLICY changes_select ON changes FOR SELECT
    USING (organization_id = auth_org_id());

-- Evidence bundles: read-only for users
CREATE POLICY evidence_select ON evidence_bundles FOR SELECT
    USING (organization_id = auth_org_id());

-- Notifications: read-only for users
CREATE POLICY notifications_select ON notifications FOR SELECT
    USING (organization_id = auth_org_id());

-- Integrations: full CRUD for org
CREATE POLICY integrations_all ON integrations FOR ALL
    USING (organization_id = auth_org_id());

-- Audit log: read-only for org
CREATE POLICY audit_select ON audit_log FOR SELECT
    USING (organization_id = auth_org_id());

-- ═══════════════════════════════════════════════════════════════════════════
-- REALTIME
-- ═══════════════════════════════════════════════════════════════════════════

ALTER PUBLICATION supabase_realtime ADD TABLE watches;
ALTER PUBLICATION supabase_realtime ADD TABLE watch_runs;
ALTER PUBLICATION supabase_realtime ADD TABLE changes;

-- ═══════════════════════════════════════════════════════════════════════════
-- STORAGE (evidence bucket)
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'evidence',
    'evidence',
    false,
    52428800,
    ARRAY['image/png', 'image/jpeg', 'application/json']
)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Authenticated can read evidence"
ON storage.objects FOR SELECT
USING (bucket_id = 'evidence' AND (auth.role() = 'authenticated' OR auth.role() = 'service_role'));

CREATE POLICY "Authenticated can insert evidence"
ON storage.objects FOR INSERT
WITH CHECK (bucket_id = 'evidence' AND (auth.role() = 'authenticated' OR auth.role() = 'service_role'));
