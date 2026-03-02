"use client";

import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";
import { Clock, ArrowRight, CheckCircle2, XCircle, Loader2, Activity } from "lucide-react";

function StatusBadge({ status }: { status: Run["status"] }) {
  if (status === "running") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-medium text-amber-400 border border-amber-500/20">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
        Running
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="flex items-center gap-1.5 rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-medium text-red-400 border border-red-500/20">
        <XCircle className="h-3 w-3" />
        Failed
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-primary/15 px-2.5 py-0.5 text-xs font-medium text-primary border border-primary/20">
      <CheckCircle2 className="h-3 w-3" />
      Completed
    </span>
  );
}

function formatDuration(startedAt: string, endedAt: string): string {
  const start = new Date(startedAt).getTime();
  const end = new Date(endedAt).getTime();
  if (isNaN(start) || isNaN(end)) return "--";
  const sec = Math.max(0, Math.floor((end - start) / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  return `${min}m ${s}s`;
}

function dedupeByName(steps: Run["steps"]) {
  const map = new Map<string, (typeof steps)[number]>();
  for (const s of steps) map.set(s.name, s);
  return Array.from(map.values());
}

function MiniProgress({ steps }: { steps: Run["steps"] }) {
  const unique = dedupeByName(steps);
  if (unique.length === 0) return null;
  const done = unique.filter((s) => s.status === "done").length;
  const pct = (done / unique.length) * 100;

  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] tabular-nums text-muted-foreground">
        {done}/{unique.length}
      </span>
    </div>
  );
}

export default function HistoryPage() {
  const {
    data: runs = [],
    isLoading,
  } = useSWR("runs/recent", api.runs.recent, {
    refreshInterval: 3_000,
  });

  return (
    <div className="p-6 md:p-8">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary">
          <Activity className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Run History</h1>
          <p className="text-sm text-muted-foreground">
            Recent watch runs across all watches
          </p>
        </div>
      </div>

      <div className="mt-8 space-y-2">
        {isLoading ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border bg-card/80 p-12">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">Loading runs…</span>
          </div>
        ) : runs.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/80 p-12 text-center">
            <p className="text-muted-foreground">
              No runs yet. Use the Dashboard to &quot;Run all&quot; and see runs
              here.
            </p>
          </div>
        ) : (
          runs.map((run) => {
            const unique = dedupeByName(run.steps ?? []);
            const isRunning = run.status === "running";

            return (
              <Link
                key={run.id}
                href={`/app/run/${run.id}`}
                className={`block rounded-xl border bg-card/80 px-5 py-4 card-hover transition-all ${
                  isRunning ? "border-amber-500/30" : "border-border"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <StatusBadge status={run.status} />
                    <span className="font-medium text-foreground">
                      {run.watchName ?? run.watchId}
                    </span>
                  </div>

                  <div className="flex items-center gap-4">
                    <MiniProgress steps={run.steps ?? []} />

                    {!isRunning && run.endedAt && run.startedAt && (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatDuration(run.startedAt, run.endedAt)}
                      </span>
                    )}

                    <span className="text-xs text-muted-foreground">
                      {new Date(run.startedAt).toLocaleString()}
                    </span>
                  </div>
                </div>

                <div className="mt-2 flex items-center justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    {run.selfHealed && (
                      <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] font-medium text-primary">
                        Self-healed
                      </span>
                    )}
                    {unique.length > 0 && (
                      <span className="text-xs text-muted-foreground">
                        {unique.length} agent{unique.length !== 1 ? "s" : ""}
                        {isRunning && (
                          <>
                            {" · "}
                            <span className="text-amber-400">
                              {unique.filter((s) => s.status === "running").length} active
                            </span>
                          </>
                        )}
                      </span>
                    )}
                  </div>

                  <span className="flex items-center gap-1 text-xs font-medium text-primary">
                    View detail <ArrowRight className="h-3 w-3" />
                  </span>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}
