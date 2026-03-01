"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { RunTimeline } from "@/components/run/RunTimeline";
import { DiffViewer } from "@/components/run/DiffViewer";
import { EvidenceBundle } from "@/components/run/EvidenceBundle";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, ArrowLeft, Loader2 } from "lucide-react";

export default function RunDetailPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : params.id?.[0];

  const { data: run, isLoading } = useSWR(
    id ? `run/${id}` : null,
    () => api.runs.get(id!),
    {
      // Keep refreshing if the run is still in progress
      refreshInterval: (data) =>
        !data || data.endedAt === data.startedAt ? 2000 : 0,
    }
  );

  if (isLoading || !run) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <p className="text-muted-foreground">
          {isLoading ? "Loading run…" : "Run not found."}
        </p>
        <Button variant="outline" size="sm" asChild>
          <Link href="/app">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/app" className="gap-1 text-muted-foreground">
              <ArrowLeft className="h-4 w-4" /> Back
            </Link>
          </Button>
          <h1 className="mt-2 text-2xl font-bold text-foreground">
            {run.watchName ?? run.watchId}
          </h1>
          <div className="mt-2 flex flex-wrap gap-2">
            {run.ticket.provider && (
              <Badge variant="secondary">{run.ticket.provider}</Badge>
            )}
            {run.selfHealed && <Badge variant="healthy">Self-healed</Badge>}
          </div>
        </div>
        {run.ticket.url && (
          <Button asChild className="shrink-0">
            <a
              href={run.ticket.url}
              target="_blank"
              rel="noopener noreferrer"
              className="gap-2"
            >
              Open {run.ticket.provider === "linear" ? "Linear" : "Jira"} ticket
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <RunTimeline steps={run.steps} />
        </div>
        <div className="lg:col-span-1">
          <DiffViewer diff={run.diff} impactMemo={run.impactMemo} />
        </div>
        <div className="lg:col-span-1">
          <EvidenceBundle
            artifacts={run.artifacts}
            runId={run.id}
            timestamp={run.endedAt}
          />
        </div>
      </div>
    </div>
  );
}
