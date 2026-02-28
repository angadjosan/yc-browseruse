"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listWatches, type Watch } from "@/lib/api";

export default function WatchesPage() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listWatches()
      .then(setWatches)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 rounded bg-[var(--muted)] animate-pulse" />
        <div className="mt-6 space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 rounded-xl bg-[var(--muted)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <p className="text-[var(--destructive)]">Failed to load watches: {error}</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Watches</h1>
          <p className="mt-1 text-[var(--muted-foreground)]">
            Manage compliance watches. Each watch monitors targets and runs on a schedule.
          </p>
        </div>
        <Link
          href="/watches/new"
          className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 transition-opacity"
        >
          New watch
        </Link>
      </div>

      <div className="mt-8 space-y-3">
        {watches.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-12 text-center text-[var(--muted-foreground)]">
            No watches. Create one to monitor regulations or vendor policies.
            <Link href="/watches/new" className="ml-1 text-[var(--primary)] hover:underline">
              Create watch
            </Link>
          </div>
        ) : (
          watches.map((w) => (
            <Link
              key={w.id}
              href={`/watches/${w.id}`}
              className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 card-hover"
            >
              <div>
                <p className="font-medium text-[var(--foreground)]">{w.name}</p>
                {w.description && (
                  <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">{w.description}</p>
                )}
                <p className="mt-2 text-xs text-[var(--muted-foreground)]">
                  {w.total_runs} runs · {w.total_changes} changes detected
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    w.status === "active"
                      ? "bg-[var(--primary)]/20 text-[var(--primary)]"
                      : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                  }`}
                >
                  {w.status}
                </span>
                <span className="text-[var(--muted-foreground)]">→</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
