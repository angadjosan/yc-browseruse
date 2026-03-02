-- Drop all old tables, types, functions, triggers to start fresh
-- This runs BEFORE the new consolidated schema

-- Drop triggers first
DROP TRIGGER IF EXISTS update_organizations_updated_at ON organizations;
DROP TRIGGER IF EXISTS update_watches_updated_at ON watches;
DROP TRIGGER IF EXISTS update_integrations_updated_at ON integrations;
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

-- Drop functions
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS append_run_step(UUID, TEXT) CASCADE;
DROP FUNCTION IF EXISTS handle_new_user() CASCADE;
DROP FUNCTION IF EXISTS auth_org_id() CASCADE;

-- Remove from realtime publication (ignore errors if not present)
DO $$ BEGIN
    ALTER PUBLICATION supabase_realtime DROP TABLE watches;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER PUBLICATION supabase_realtime DROP TABLE watch_runs;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
DO $$ BEGIN
    ALTER PUBLICATION supabase_realtime DROP TABLE changes;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- Drop storage policies
DROP POLICY IF EXISTS "Authenticated can read evidence" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated can insert evidence" ON storage.objects;

-- Drop all RLS policies
DO $$ DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT schemaname, tablename, policyname
        FROM pg_policies
        WHERE schemaname = 'public'
    ) LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I.%I', r.policyname, r.schemaname, r.tablename);
    END LOOP;
END $$;

-- Drop tables in dependency order
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS evidence_bundles CASCADE;
DROP TABLE IF EXISTS changes CASCADE;
DROP TABLE IF EXISTS snapshots CASCADE;
DROP TABLE IF EXISTS watch_runs CASCADE;
DROP TABLE IF EXISTS watches CASCADE;
DROP TABLE IF EXISTS integrations CASCADE;
DROP TABLE IF EXISTS api_keys CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS organizations CASCADE;

-- Drop enums
DROP TYPE IF EXISTS watch_status CASCADE;
DROP TYPE IF EXISTS run_status CASCADE;
DROP TYPE IF EXISTS impact_level CASCADE;
DROP TYPE IF EXISTS user_role CASCADE;
DROP TYPE IF EXISTS notification_channel CASCADE;
DROP TYPE IF EXISTS notification_status CASCADE;
DROP TYPE IF EXISTS integration_service CASCADE;

-- Storage bucket cleanup skipped (managed via Storage API)
