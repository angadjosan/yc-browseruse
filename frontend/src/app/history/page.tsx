"use client";

import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";

function StatusBadge({ status }: { status: Run["status"] }) {
  if (status === "running") {
    return (
      <span className="flex items-center gap-1 rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs font-medium text-yellow-400">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-yellow-400" />
        running
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
        failed
      </span>
    );
  }
  return (
    <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
      completed
    </span>
  );
}

export default function HistoryPage() {
  const { data: runs = [], isLoading } = useSWR("runs/recent", api.runs.recent, {
    refreshInterval: 3_000,
  });

  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-foreground">Run history</h1>
      <p className="mt-1 text-muted-foreground">
        Recent watch runs across all watches.
      </p>

      <div className="mt-8 space-y-2">
        {isLoading ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            Loading runs…
          </div>
        ) : runs.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            No runs yet. Use the Dashboard to &quot;Run all&quot; and see runs here.
          </div>
        ) : (
          runs.map((run) => (
            <div
              key={run.id}
              className="rounded-xl border border-border bg-card/80 px-4 py-3 card-hover"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-4">
                  <StatusBadge status={run.status} />
                  <Link
                    href={`/app/run/${run.id}`}
                    className="font-medium text-foreground hover:text-primary"
                  >
                    {run.watchName ?? run.watchId}
                  </Link>
                  <span className="text-sm text-muted-foreground">
                    {new Date(run.startedAt).toLocaleString()}
                  </span>
                  {run.selfHealed && (
                    <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                      Self-healed
                    </span>
                  )}
                </div>
                <div className="text-sm text-muted-foreground">
                  {run.steps.length} steps · {run.artifacts.length} artifacts
                </div>
              </div>
              <div className="mt-2">
                <Link
                  href={`/app/run/${run.id}`}
                  className="text-xs font-medium text-primary hover:underline"
                >
                  View run detail →
                </Link>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
