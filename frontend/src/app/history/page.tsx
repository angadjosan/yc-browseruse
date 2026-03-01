"use client";

import Link from "next/link";
import { runs } from "@/lib/mockData";

export default function HistoryPage() {
  return (
    <div className="p-6 md:p-8">
      <h1 className="text-2xl font-bold text-foreground">Run history</h1>
      <p className="mt-1 text-muted-foreground">
        Recent watch runs across all watches. (Mock data — no backend.)
      </p>

      <div className="mt-8 space-y-2">
        {runs.length === 0 ? (
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
                  <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs font-medium text-primary">
                    completed
                  </span>
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
