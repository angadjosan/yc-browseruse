"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getRecentRuns, type RecentRun } from "@/lib/api";

export default function HistoryPage() {
  const [runs, setRuns] = useState<RecentRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getRecentRuns(50)
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 rounded bg-[var(--muted)] animate-pulse" />
        <div className="mt-6 space-y-2">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-14 rounded-xl bg-[var(--muted)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <p className="text-[var(--destructive)]">Failed to load history: {error}</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-[var(--foreground)]">Run history</h1>
      <p className="mt-1 text-[var(--muted-foreground)]">
        Recent watch runs across all watches.
      </p>

      <div className="mt-8 space-y-2">
        {runs.length === 0 ? (
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-8 text-center text-[var(--muted-foreground)]">
            No runs yet. Run a watch from the Watches page to see history here.
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3"
            >
              <div className="flex items-center gap-4">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                    run.status === "completed"
                      ? "bg-[var(--primary)]/20 text-[var(--primary)]"
                      : run.status === "failed"
                      ? "bg-[var(--destructive)]/20 text-[var(--destructive)]"
                      : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {run.status}
                </span>
                <Link
                  href={`/watches/${run.watch_id}`}
                  className="font-medium text-[var(--foreground)] hover:text-[var(--primary)]"
                >
                  {(run as RecentRun).watch_name || run.watch_id}
                </Link>
                <span className="text-sm text-[var(--muted-foreground)]">
                  {new Date(run.started_at).toLocaleString()}
                </span>
                {run.duration_ms != null && (
                  <span className="text-xs text-[var(--muted-foreground)]">{run.duration_ms}ms</span>
                )}
              </div>
              <div className="text-sm text-[var(--muted-foreground)]">
                {run.tasks_executed} tasks · {run.changes_detected} changes
                {run.error_message && (
                  <span className="ml-2 text-[var(--destructive)]" title={run.error_message}>
                    Error
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
