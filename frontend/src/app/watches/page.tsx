"use client";

import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";

export default function WatchesPage() {
  const { data: watches = [], isLoading } = useSWR("watches", api.watches.list, {
    refreshInterval: 30_000,
  });

  return (
    <div className="p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Watches</h1>
          <p className="mt-1 text-muted-foreground">
            Manage compliance watches. Each watch monitors targets and runs on a schedule.
          </p>
        </div>
        <Link
          href="/watches/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity shrink-0"
        >
          New watch
        </Link>
      </div>

      <div className="mt-8 space-y-3">
        {isLoading ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            Loading watches…
          </div>
        ) : watches.length === 0 ? (
          <div className="rounded-xl border border-border border-dashed bg-card/80 p-12 text-center text-muted-foreground">
            No watches. Create one to monitor regulations or vendor policies.{" "}
            <Link href="/watches/new" className="text-primary hover:underline">
              Create watch
            </Link>
          </div>
        ) : (
          watches.map((w) => (
            <Link
              key={w.id}
              href={`/watches/${w.id}`}
              className="flex items-center justify-between rounded-xl border border-border bg-card/80 p-5 card-hover"
            >
              <div>
                <p className="font-medium text-foreground">{w.name}</p>
                <p className="mt-0.5 text-sm text-muted-foreground">{w.description}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {w.nextRunAt
                    ? `Next run: ${new Date(w.nextRunAt).toLocaleString()}`
                    : "No next run scheduled"}
                  {w.lastRunAt && ` · Last: ${new Date(w.lastRunAt).toLocaleString()}`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    w.status === "healthy"
                      ? "bg-primary/20 text-primary"
                      : "bg-warning/20 text-warning"
                  }`}
                >
                  {w.status}
                </span>
                <span className="text-muted-foreground">→</span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
