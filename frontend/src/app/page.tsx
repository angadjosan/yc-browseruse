"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listWatches, type Watch } from "@/lib/api";

function StatCard({
  title,
  value,
  sub,
  href,
}: {
  title: string;
  value: string | number;
  sub?: string;
  href?: string;
}) {
  const content = (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 card-hover">
      <p className="text-xs font-medium uppercase tracking-wider text-[var(--muted-foreground)]">{title}</p>
      <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">{value}</p>
      {sub && <p className="mt-0.5 text-sm text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  );
  if (href) return <Link href={href}>{content}</Link>;
  return content;
}

export default function DashboardPage() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listWatches()
      .then(setWatches)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const totalRuns = watches.reduce((a, w) => a + w.total_runs, 0);
  const totalChanges = watches.reduce((a, w) => a + w.total_changes, 0);
  const activeWatches = watches.filter((w) => w.status === "active").length;

  if (loading) {
    return (
      <div className="p-8">
        <div className="h-8 w-48 rounded bg-[var(--muted)] animate-pulse" />
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-28 rounded-xl bg-[var(--muted)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <p className="text-[var(--destructive)]">Failed to load: {error}</p>
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">Ensure the API is running at {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}</p>
      </div>
    );
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-[var(--foreground)]">Dashboard</h1>
      <p className="mt-1 text-[var(--muted-foreground)]">
        Overview of your compliance watches and change detection.
      </p>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        <StatCard title="Active watches" value={activeWatches} sub={`of ${watches.length} total`} href="/watches" />
        <StatCard title="Total runs" value={totalRuns} sub="All time" href="/history" />
        <StatCard title="Changes detected" value={totalChanges} sub="Require review" href="/evidence" />
      </div>

      <section className="mt-10">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--foreground)]">Recent watches</h2>
          <Link
            href="/watches/new"
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 transition-opacity"
          >
            Add watch
          </Link>
        </div>
        <div className="mt-4 space-y-3">
          {watches.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center text-[var(--muted-foreground)]">
              No watches yet. Create one to start monitoring regulations and vendor policies.
              <br />
              <Link href="/watches/new" className="mt-3 inline-block text-[var(--primary)] hover:underline">
                Create your first watch →
              </Link>
            </div>
          ) : (
            watches.slice(0, 5).map((w) => (
              <Link
                key={w.id}
                href={`/watches/${w.id}`}
                className="block rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 card-hover"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-[var(--foreground)]">{w.name}</p>
                    <p className="text-sm text-[var(--muted-foreground)]">
                      {w.total_runs} runs · {w.total_changes} changes
                    </p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      w.status === "active"
                        ? "bg-[var(--primary)]/20 text-[var(--primary)]"
                        : "bg-[var(--muted)] text-[var(--muted-foreground)]"
                    }`}
                  >
                    {w.status}
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
