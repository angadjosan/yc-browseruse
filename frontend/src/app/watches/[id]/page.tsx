"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { getWatch, getWatchHistory, runWatch, type Watch, type WatchRun } from "@/lib/api";

export default function WatchDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [watch, setWatch] = useState<Watch | null>(null);
  const [runs, setRuns] = useState<WatchRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getWatch(id), getWatchHistory(id, 20)])
      .then(([w, h]) => {
        setWatch(w);
        setRuns(h.runs);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleRunNow() {
    if (!watch) return;
    setRunning(true);
    setError(null);
    try {
      await runWatch(watch.id);
      const [w, h] = await Promise.all([getWatch(id), getWatchHistory(id, 20)]);
      setWatch(w);
      setRuns(h.runs);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-64 rounded bg-[var(--muted)] animate-pulse" />
        <div className="mt-8 h-48 rounded-xl bg-[var(--muted)] animate-pulse" />
      </div>
    );
  }

  if (error && !watch) {
    return (
      <div className="p-8">
        <p className="text-[var(--destructive)]">Failed to load watch: {error}</p>
        <Link href="/watches" className="mt-2 inline-block text-[var(--primary)] hover:underline">
          Back to watches
        </Link>
      </div>
    );
  }

  if (!watch) return null;

  return (
    <div className="p-8">
      <Link href="/watches" className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        ← Watches
      </Link>
      <div className="mt-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">{watch.name}</h1>
          {watch.description && (
            <p className="mt-1 text-[var(--muted-foreground)]">{watch.description}</p>
          )}
          <div className="mt-2 flex items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                watch.status === "active"
                  ? "bg-[var(--primary)]/20 text-[var(--primary)]"
                  : "bg-[var(--muted)] text-[var(--muted-foreground)]"
              }`}
            >
              {watch.status}
            </span>
            <span className="text-sm text-[var(--muted-foreground)]">
              {watch.total_runs} runs · {watch.total_changes} changes
            </span>
          </div>
        </div>
        <button
          onClick={handleRunNow}
          disabled={running}
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          {running ? "Running…" : "Run now"}
        </button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-[var(--destructive)]/50 bg-[var(--destructive)]/10 px-4 py-3 text-sm text-[var(--destructive)]">
          {error}
        </div>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-[var(--foreground)]">Run history</h2>
        <div className="mt-4 space-y-2">
          {runs.length === 0 ? (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 text-center text-[var(--muted-foreground)]">
              No runs yet. Click “Run now” to execute this watch.
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
      </section>
    </div>
  );
}
