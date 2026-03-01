"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import type { ChangeEvent } from "@/lib/types";
import { AlertTriangle } from "lucide-react";
import { LinearIcon } from "@/components/ui/linear-icon";

const severityColors = {
  high: "bg-destructive/20 text-destructive border-destructive/30",
  med: "bg-warning/20 text-warning border-warning/30",
  low: "bg-muted text-muted-foreground border-border",
} as const;

type Filter = "all" | "high" | "med" | "low";

export default function AlertsPage() {
  const [filter, setFilter] = useState<Filter>("all");

  const { data: changes = [], isLoading } = useSWR(
    "alerts-all",
    () => api.changes.list(50),
    { refreshInterval: 30_000 }
  );

  const filtered =
    filter === "all" ? changes : changes.filter((c) => c.severity === filter);

  return (
    <div className="p-6 md:p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-6 w-6 text-warning" />
        <div>
          <h1 className="text-2xl font-bold text-foreground">Alerts</h1>
          <p className="text-muted-foreground">
            Regulatory shifts detected across your watches
          </p>
        </div>
      </div>

      {/* Severity filter chips */}
      <div className="mt-6 flex gap-2">
        {(["all", "high", "med", "low"] as const).map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              filter === level
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {level === "all" ? "All" : level === "med" ? "Medium" : level.charAt(0).toUpperCase() + level.slice(1)}
          </button>
        ))}
      </div>

      {/* Alert list */}
      <div className="mt-6 space-y-3">
        {isLoading ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            Loading alerts...
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            {filter === "all"
              ? "No alerts yet. Run a watch to detect regulatory changes."
              : `No ${filter} severity alerts.`}
          </div>
        ) : (
          filtered.map((c: ChangeEvent) => (
            <Link
              key={c.id}
              href={`/app/run/${c.runId}`}
              className="block rounded-xl border border-border bg-card/80 p-4 transition-colors hover:border-primary/30 card-hover"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${severityColors[c.severity]}`}
                    >
                      {c.severity}
                    </span>
                    <span className="truncate text-sm font-medium text-foreground">
                      {c.title}
                    </span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded bg-primary/10 px-1.5 py-0.5 text-primary">
                      {c.jurisdiction}
                    </span>
                    <span>{new Date(c.createdAt).toLocaleString()}</span>
                  </div>
                  {c.memo && (
                    <p className="mt-2 text-xs text-muted-foreground line-clamp-2">
                      {c.memo}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {c.linearTicketUrl && (
                    <a
                      href={c.linearTicketUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="inline-flex items-center gap-1.5 rounded-md bg-[#5E6AD2]/10 px-2.5 py-1 text-xs font-medium text-[#5E6AD2] transition-colors hover:bg-[#5E6AD2]/20"
                    >
                      <LinearIcon className="h-3.5 w-3.5" />
                      View in Linear
                    </a>
                  )}
                  <span className="text-xs text-muted-foreground">
                    View &rarr;
                  </span>
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}
