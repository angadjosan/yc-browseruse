"use client";

export default function SettingsPage() {
  return (
    <div className="p-8 max-w-2xl">
      <h1 className="text-2xl font-bold text-[var(--foreground)]">Settings</h1>
      <p className="mt-1 text-[var(--muted-foreground)]">
        Integrations and API keys are configured via environment variables on the server.
      </p>

      <div className="mt-10 space-y-8">
        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Integrations</h2>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Configure Linear and Slack in the backend <code className="rounded bg-[var(--muted)] px-1">.env</code>.
            When a watch detects a change, the system will create a Linear issue and send a Slack notification if
            keys and team/channel are set.
          </p>
          <ul className="mt-4 space-y-2 text-sm text-[var(--muted-foreground)]">
            <li><strong className="text-[var(--foreground)]">Linear:</strong> <code>LINEAR_API_KEY</code>; set <code>integrations.linear_team_id</code> per watch.</li>
            <li><strong className="text-[var(--foreground)]">Slack:</strong> <code>SLACK_BOT_TOKEN</code>; set <code>integrations.slack_channel</code> per watch.</li>
          </ul>
        </section>

        <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">API keys (backend)</h2>
          <p className="mt-2 text-sm text-[var(--muted-foreground)]">
            Add these to a gitignored <code className="rounded bg-[var(--muted)] px-1">.env</code> in the project root or backend:
          </p>
          <ul className="mt-4 space-y-1 text-sm text-[var(--muted-foreground)]">
            <li><code>SUPABASE_URL</code>, <code>SUPABASE_SERVICE_ROLE_KEY</code></li>
            <li><code>ANTHROPIC_API_KEY</code> (Claude — orchestrator)</li>
            <li><code>BROWSER_USE_API_KEY</code> (browser automation)</li>
            <li><code>LINEAR_API_KEY</code>, <code>SLACK_BOT_TOKEN</code></li>
            <li><code>EVIDENCE_SIGNING_KEY</code> (HMAC for evidence integrity)</li>
          </ul>
        </section>
      </div>
    </div>
  );
}
