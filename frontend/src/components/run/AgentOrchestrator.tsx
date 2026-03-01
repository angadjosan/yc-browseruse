"use client";

import { useState } from "react";
import type { Run, RunStep, AgentThought } from "@/lib/types";
import {
  Brain,
  CheckCircle2,
  RefreshCw,
  Clock,
  Loader2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

type Props = {
  run: Run;
};

const statusConfig = {
  running: {
    color: "border-amber-500 bg-amber-500/10 text-amber-400",
    ring: "ring-amber-500/30",
    icon: Loader2,
    iconClass: "animate-spin",
    label: "Running",
  },
  done: {
    color: "border-emerald-500 bg-emerald-500/10 text-emerald-400",
    ring: "ring-emerald-500/30",
    icon: CheckCircle2,
    iconClass: "",
    label: "Done",
  },
  retry: {
    color: "border-red-500 bg-red-500/10 text-red-400",
    ring: "ring-red-500/30",
    icon: RefreshCw,
    iconClass: "",
    label: "Retry",
  },
  pending: {
    color: "border-zinc-600 bg-zinc-800/50 text-zinc-500",
    ring: "ring-zinc-600/30",
    icon: Clock,
    iconClass: "",
    label: "Pending",
  },
} as const;

function getStepStatus(step: RunStep) {
  const s = step.status as keyof typeof statusConfig;
  return statusConfig[s] || statusConfig.pending;
}

export function AgentOrchestrator({ run }: Props) {
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  const isRunning = run.status === "running";
  const steps = run.steps || [];
  const thoughts = run.agentThoughts || [];

  // Find thoughts matching a step by target_name
  function findThoughts(stepName: string): AgentThought | undefined {
    return thoughts.find(
      (t) =>
        t.target_name === stepName ||
        stepName.startsWith(t.target_name?.slice(0, 20) ?? "")
    );
  }

  const activeCount = steps.filter((s) => s.status === "running").length;
  const doneCount = steps.filter((s) => s.status === "done").length;

  return (
    <div className="space-y-8">
      {/* Claude orchestrator node */}
      <div className="flex flex-col items-center">
        <div
          className={`relative flex h-24 w-24 flex-col items-center justify-center rounded-full border-2 ${
            isRunning
              ? "border-primary bg-primary/10 text-primary"
              : "border-emerald-500 bg-emerald-500/10 text-emerald-400"
          }`}
        >
          {isRunning && (
            <div className="absolute inset-0 animate-ping rounded-full border border-primary/30" />
          )}
          <Brain className="h-8 w-8" />
        </div>
        <p className="mt-3 text-sm font-semibold text-foreground">
          Claude Orchestrator
        </p>
        <p className="text-xs text-muted-foreground">
          {isRunning
            ? `Orchestrating ${activeCount} agent${activeCount !== 1 ? "s" : ""}...`
            : run.agentSummary
              ? run.agentSummary.slice(0, 100)
              : `Completed ${doneCount} agent${doneCount !== 1 ? "s" : ""}`}
        </p>
      </div>

      {/* Connector line */}
      {steps.length > 0 && (
        <div className="flex justify-center">
          <div className="h-8 w-px bg-border" />
        </div>
      )}

      {/* BU agent nodes */}
      {steps.length > 0 && (
        <div className="flex flex-wrap justify-center gap-4">
          {steps.map((step, i) => {
            const cfg = getStepStatus(step);
            const Icon = cfg.icon;
            const isExpanded = expandedAgent === step.name;
            const agentThoughts = findThoughts(step.name);

            return (
              <div key={`${step.name}-${i}`} className="flex flex-col items-center">
                {/* Connector stub */}
                <div className="h-4 w-px bg-border" />

                {/* Agent circle */}
                <button
                  onClick={() =>
                    setExpandedAgent(isExpanded ? null : step.name)
                  }
                  className={`group relative flex h-14 w-14 items-center justify-center rounded-full border-2 transition-all hover:ring-2 ${cfg.color} ${cfg.ring}`}
                >
                  {step.status === "running" && (
                    <div className="absolute inset-0 animate-ping rounded-full border border-amber-500/20" />
                  )}
                  <Icon className={`h-5 w-5 ${cfg.iconClass}`} />
                </button>

                {/* Label */}
                <p
                  className="mt-1.5 max-w-[100px] truncate text-center text-xs text-muted-foreground"
                  title={step.name}
                >
                  {step.name}
                </p>
                <span className={`text-[10px] font-medium ${cfg.color.split(" ").pop()}`}>
                  {cfg.label}
                </span>

                {/* Expand indicator */}
                <button
                  onClick={() =>
                    setExpandedAgent(isExpanded ? null : step.name)
                  }
                  className="mt-0.5 text-muted-foreground hover:text-foreground"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-3 w-3" />
                  ) : (
                    <ChevronRight className="h-3 w-3" />
                  )}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Expanded agent detail panel */}
      {expandedAgent && (
        <div className="rounded-xl border border-border bg-card/80 p-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">
              {expandedAgent}
            </h3>
            <button
              onClick={() => setExpandedAgent(null)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Close
            </button>
          </div>

          <div className="mt-3 space-y-2">
            {(() => {
              const at = findThoughts(expandedAgent);
              if (!at || !at.thoughts || at.thoughts.length === 0) {
                return (
                  <p className="text-xs text-muted-foreground italic">
                    {isRunning ? "Agent working..." : "No thoughts recorded."}
                  </p>
                );
              }

              return at.thoughts.map((thought, i) => {
                const goal =
                  (thought as Record<string, any>).current_state?.next_goal ||
                  (thought as Record<string, any>).thought ||
                  (thought as Record<string, any>).text ||
                  "Processing...";
                const reasoning =
                  (thought as Record<string, any>).current_state
                    ?.internal_reasoning ||
                  (thought as Record<string, any>).reasoning ||
                  "";

                return (
                  <div
                    key={i}
                    className="flex gap-3 border-l-2 border-primary/30 pl-3"
                  >
                    <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/50" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-foreground">
                        {String(goal).slice(0, 120)}
                      </p>
                      {reasoning && (
                        <p className="mt-0.5 text-[11px] text-muted-foreground">
                          {String(reasoning).slice(0, 200)}
                        </p>
                      )}
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        </div>
      )}

      {/* Agent summary when complete */}
      {!isRunning && run.agentSummary && (
        <div className="rounded-xl border border-border bg-card/80 p-4">
          <h3 className="text-sm font-semibold text-foreground">
            Run Summary
          </h3>
          <p className="mt-2 text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {run.agentSummary}
          </p>
        </div>
      )}
    </div>
  );
}
