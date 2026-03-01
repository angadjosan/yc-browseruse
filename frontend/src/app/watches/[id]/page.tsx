"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { api } from "@/lib/api";

export default function WatchDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const { data: watch, isLoading: watchLoading } = useSWR(
    id ? `watch/${id}` : null,
    () => api.watches.get(id)
  );
  const { data: watchRuns = [], isLoading: runsLoading } = useSWR(
    id ? `watch/${id}/runs` : null,
    () => api.watches.runs(id),
    { refreshInterval: 15_000 }
  );

  if (watchLoading) {
    return (
      <div className="p-6 md:p-8">
        <p className="text-muted-foreground">Loading watch…</p>
      </div>
    );
  }

  if (!watch) {
    return (
      <div className="p-6 md:p-8">
        <p className="text-destructive">Watch not found.</p>
        <Link href="/watches" className="mt-2 inline-block text-primary hover:underline">
          Back to watches
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8">
      <Link
        href="/watches"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        ← Watches
      </Link>
      <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{watch.name}</h1>
          <p className="mt-1 text-muted-foreground">{watch.description}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                watch.status === "healthy"
                  ? "bg-primary/20 text-primary"
                  : "bg-warning/20 text-warning"
              }`}
            >
              {watch.status}
            </span>
            {watch.nextRunAt && (
              <span className="text-sm text-muted-foreground">
                Next run: {new Date(watch.nextRunAt).toLocaleString()}
              </span>
            )}
            {watch.jurisdictions.length > 0 && (
              <span className="text-sm text-muted-foreground">
                {watch.jurisdictions.join(", ")}
              </span>
            )}
          </div>
        </div>
      </div>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-foreground">Run history</h2>
        <div className="mt-4 space-y-2">
          {runsLoading ? (
            <div className="rounded-xl border border-border bg-card/80 p-6 text-center text-muted-foreground">
              Loading runs…
            </div>
          ) : watchRuns.length === 0 ? (
            <div className="rounded-xl border border-border bg-card/80 p-6 text-center text-muted-foreground">
              No runs yet. Use the Dashboard &quot;Run all&quot; to execute watches.
            </div>
          ) : (
            watchRuns.map((run) => (
              <Link
                key={run.id}
                href={`/app/run/${run.id}`}
                className="block rounded-xl border border-border bg-card/80 px-4 py-3 card-hover"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-4">
                    <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
                      completed
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {new Date(run.startedAt).toLocaleString()}
                    </span>
                    {run.selfHealed && (
                      <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                        Self-healed
                      </span>
                    )}
                  </div>
                  <span className="text-sm text-muted-foreground">
                    View run detail →
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
