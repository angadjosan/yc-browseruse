"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useRunStream } from "@/lib/useRunStream";
import { DiffViewer } from "@/components/run/DiffViewer";
import { AgentOrchestrator } from "@/components/run/AgentOrchestrator";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, Loader2, Radio } from "lucide-react";
import { LinearIcon } from "@/components/ui/linear-icon";

export default function RunDetailPage() {
  const params = useParams();
  const id = typeof params.id === "string" ? params.id : params.id?.[0];

  const { run, error, isLoading, isStreaming } = useRunStream(id);

  const isRunning = run?.status === "running";

  if (isLoading && !run) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <div className="relative">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <div className="absolute inset-0 animate-ping rounded-full border border-primary/20" />
        </div>
        <div className="text-center">
          <p className="font-medium text-foreground">Connecting to run…</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Establishing stream connection
          </p>
        </div>
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

  const stepsDone = (run.steps ?? []).filter(
    (s, i, a) =>
      s.status === "done" && a.findIndex((x) => x.name === s.name) === i
  );
  const uniqueStepNames = new Set((run.steps ?? []).map((s) => s.name));

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
              <Badge
                variant="secondary"
                className="gap-1 border-amber-500/50 bg-amber-500/10 text-amber-400"
              >
                <Radio className="h-3 w-3 animate-pulse" /> Running
              </Badge>
            ) : run.status === "failed" ? (
              <Badge variant="destructive">Failed</Badge>
            ) : (
              <Badge variant="healthy">Completed</Badge>
            )}
            {isRunning && uniqueStepNames.size > 0 && (
              <span className="text-xs text-muted-foreground">
                {stepsDone.length}/{uniqueStepNames.size} agents
              </span>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {run.selfHealed && <Badge variant="healthy">Self-healed</Badge>}
          </div>
        </div>
        {!isRunning && run.ticket?.url && (
          <a
            href={run.ticket.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-[#5E6AD2]/20 bg-[#5E6AD2]/10 px-4 py-2 text-sm font-medium text-[#5E6AD2] transition-colors hover:bg-[#5E6AD2]/20"
          >
            <LinearIcon className="h-4 w-4" />
            View Linear issue
          </a>
        )}
      </div>

      {/* Content */}
      {isRunning ? (
        <AgentOrchestrator run={run} isStreaming={isStreaming} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <AgentOrchestrator run={run} />
          <DiffViewer diff={run.diff} impactMemo={run.impactMemo} />
        </div>
      )}
    </div>
  );
}
