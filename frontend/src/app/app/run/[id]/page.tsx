"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import useSWR from "swr";
import { api } from "@/lib/api";
import { RunTimeline } from "@/components/run/RunTimeline";
import { DiffViewer } from "@/components/run/DiffViewer";
import { AgentOrchestrator } from "@/components/run/AgentOrchestrator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, ArrowLeft, Loader2, Radio } from "lucide-react";

function useRunWithRetry(runId: string | undefined) {
  const { data: run, error, isLoading } = useSWR(
    runId ? `run/${runId}` : null,
    () => api.runs.get(runId!),
    {
      refreshInterval: (data) =>
        !data || data.status === "running" ? 2000 : 0,
      errorRetryCount: 10,
      errorRetryInterval: 2000,
      shouldRetryOnError: true,
    }
  );
  return { run, error, isLoading };
}

export default function RunDetailPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : params.id?.[0];

  const { run, error, isLoading } = useRunWithRetry(id);

  const isRunning = run?.status === "running";

  if (isLoading && !run) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <p className="text-muted-foreground">Run is starting...</p>
        <Button variant="outline" size="sm" asChild>
          <Link href="/app">
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Dashboard
          </Link>
        </Button>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <p className="text-muted-foreground">
          Run not found. It may still be starting or the run ID is invalid.
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
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/app" className="gap-1 text-muted-foreground">
              <ArrowLeft className="h-4 w-4" /> Back
            </Link>
          </Button>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-bold text-foreground">
              {run.watchName ?? run.watchId}
            </h1>
            {isRunning ? (
              <Badge variant="secondary" className="gap-1 border-amber-500/50 bg-amber-500/10 text-amber-400">
                <Radio className="h-3 w-3 animate-pulse" /> Running
              </Badge>
            ) : run.status === "failed" ? (
              <Badge variant="destructive">Failed</Badge>
            ) : (
              <Badge variant="healthy">Completed</Badge>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {run.ticket.provider && run.ticket.url && (
              <Badge variant="secondary">{run.ticket.provider}</Badge>
            )}
            {run.selfHealed && <Badge variant="healthy">Self-healed</Badge>}
          </div>
        </div>
        {!isRunning && run.ticket.url && (
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

      {/* Content: two modes */}
      {isRunning ? (
        /* Running mode: full-width orchestrator tree */
        <AgentOrchestrator run={run} />
      ) : (
        /* Completed mode: timeline + diff viewer, 2 columns */
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <RunTimeline steps={run.steps} />
          </div>
          <div>
            <DiffViewer diff={run.diff} impactMemo={run.impactMemo} />
          </div>
        </div>
      )}
    </div>
  );
}
