"use client";

import { useState } from "react";
import type { Run, RunStep, AgentThought } from "@/lib/types";
import {
  Brain,
  CheckCircle2,
  RefreshCw,
  Clock,
  Loader2,
  X,
  Network,
  Globe,
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

function getStepCfg(step: RunStep) {
  const s = step.status as keyof typeof statusConfig;
  return statusConfig[s] ?? statusConfig.pending;
}

/** Keep only the latest status per agent name (backend appends running + done entries). */
function dedupeSteps(steps: RunStep[]): RunStep[] {
  const map = new Map<string, RunStep>();
  for (const step of steps) {
    map.set(step.name, step);
  }
  return Array.from(map.values());
}

// ── Workflow panel: orchestrator ──────────────────────────────────────────────

function OrchestratorWorkflow({
  run,
  steps,
}: {
  run: Run;
  steps: RunStep[];
}) {
  const isRunning = run.status === "running";

  if (steps.length === 0) {
    return (
      <p className="text-xs italic text-muted-foreground">
        {isRunning ? "Waiting for agents to spawn…" : "No agents recorded."}
      </p>
    );
  }

  const runningCount = steps.filter((s) => s.status === "running").length;
  const doneCount = steps.filter((s) => s.status === "done").length;

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {isRunning
          ? `${runningCount} running · ${doneCount} done`
          : `${doneCount} of ${steps.length} agents completed`}
      </p>

      <div className="space-y-2">
        {steps.map((step, i) => {
          const cfg = getStepCfg(step);
          const Icon = cfg.icon;
          const textColor = cfg.color.split(" ").at(-1)!;
          return (
            <div
              key={step.name}
              className="flex items-start gap-3 border-l-2 border-border pl-3"
            >
              <div className="mt-0.5 flex shrink-0 items-center gap-1.5">
                <span className="w-4 text-right font-mono text-[10px] text-muted-foreground/50">
                  {i + 1}
                </span>
                <Icon className={`h-3.5 w-3.5 ${cfg.iconClass} ${textColor}`} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium leading-snug text-foreground">
                  {step.name}
                </p>
                <div className="mt-0.5 flex items-center gap-2">
                  <span className={`text-[10px] font-medium ${textColor}`}>
                    {cfg.label}
                  </span>
                  {step.timestamp && (
                    <span className="text-[10px] text-muted-foreground/40">
                      {new Date(step.timestamp).toLocaleTimeString()}
                    </span>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {run.agentSummary && (
        <div className="mt-4 border-t border-border pt-4">
          <p className="mb-1 text-[11px] font-medium text-muted-foreground">
            Summary
          </p>
          <p className="text-xs leading-relaxed text-foreground/80 whitespace-pre-wrap">
            {run.agentSummary}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Workflow panel: browser-use subagent ──────────────────────────────────────

function SubagentWorkflow({
  step,
  thoughts,
}: {
  step: RunStep;
  thoughts: AgentThought | undefined;
}) {
  if (!thoughts?.thoughts?.length) {
    return (
      <p className="text-xs italic text-muted-foreground">
        {step.status === "running"
          ? "Agent working — thought log will appear when complete."
          : "No workflow data recorded for this agent."}
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {thoughts.thoughts.length} step
        {thoughts.thoughts.length !== 1 ? "s" : ""} recorded
      </p>

      <div className="space-y-3">
        {thoughts.thoughts.map((thought, i) => {
          const t = thought as Record<string, any>;
          const goal =
            t.current_state?.next_goal || t.thought || t.text || "Processing…";
          const reasoning =
            t.current_state?.internal_reasoning || t.reasoning || "";
          const action = t.action?.name || t.current_state?.action || "";

          return (
            <div key={i} className="flex gap-3 border-l-2 border-primary/30 pl-3">
              <div className="mt-0.5 shrink-0">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 font-mono text-[10px] font-bold text-primary">
                  {i + 1}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium leading-snug text-foreground">
                  {String(goal)}
                </p>
                {action && (
                  <p className="mt-0.5 font-mono text-[10px] text-primary/70">
                    → {String(action)}
                  </p>
                )}
                {reasoning && (
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {String(reasoning)}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AgentOrchestrator({ run }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<
    "orchestrator" | string | null
  >(null);

  const isRunning = run.status === "running";
  const steps = dedupeSteps(run.steps ?? []);
  const thoughts = run.agentThoughts ?? [];

  function findThoughts(stepName: string): AgentThought | undefined {
    return thoughts.find(
      (t) =>
        t.target_name === stepName ||
        stepName.startsWith(t.target_name?.slice(0, 20) ?? "")
    );
  }

  const activeCount = steps.filter((s) => s.status === "running").length;
  const doneCount = steps.filter((s) => s.status === "done").length;

  const selectedStep =
    selectedAgent && selectedAgent !== "orchestrator"
      ? steps.find((s) => s.name === selectedAgent) ?? null
      : null;

  return (
    <div className="space-y-8">
      {/* Claude orchestrator node */}
      <div className="flex flex-col items-center">
        <button
          onClick={() =>
            setSelectedAgent(
              selectedAgent === "orchestrator" ? null : "orchestrator"
            )
          }
          className={`relative flex h-24 w-24 flex-col items-center justify-center rounded-full border-2 transition-all hover:ring-2 hover:ring-primary/40 ${
            isRunning
              ? "border-primary bg-primary/10 text-primary"
              : "border-emerald-500 bg-emerald-500/10 text-emerald-400"
          } ${selectedAgent === "orchestrator" ? "ring-2 ring-primary/40" : ""}`}
        >
          {isRunning && (
            <div className="absolute inset-0 animate-ping rounded-full border border-primary/30" />
          )}
          <Brain className="h-8 w-8" />
        </button>
        <p className="mt-3 text-sm font-semibold text-foreground">
          Claude Orchestrator
        </p>
        <p className="text-xs text-muted-foreground">
          {isRunning
            ? `Orchestrating ${activeCount} agent${activeCount !== 1 ? "s" : ""}…`
            : `Completed ${doneCount} agent${doneCount !== 1 ? "s" : ""}`}
        </p>
        <p className="mt-0.5 text-[10px] text-muted-foreground/40">
          click to inspect
        </p>
      </div>

      {/* Connector line */}
      {steps.length > 0 && (
        <div className="flex justify-center">
          <div className="h-8 w-px bg-border" />
        </div>
      )}

      {/* Subagent nodes — pop in as they're created */}
      {steps.length > 0 && (
        <div className="flex flex-wrap justify-center gap-4">
          {steps.map((step, i) => {
            const cfg = getStepCfg(step);
            const Icon = cfg.icon;
            const textColor = cfg.color.split(" ").at(-1)!;
            const isSelected = selectedAgent === step.name;

            return (
              <div
                key={step.name}
                className="agent-pop-in flex flex-col items-center"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <div className="h-4 w-px bg-border" />

                <button
                  onClick={() =>
                    setSelectedAgent(isSelected ? null : step.name)
                  }
                  className={`group relative flex h-14 w-14 items-center justify-center rounded-full border-2 transition-all hover:ring-2 ${cfg.color} ${cfg.ring} ${isSelected ? "ring-2" : ""}`}
                >
                  {step.status === "running" && (
                    <div className="absolute inset-0 animate-ping rounded-full border border-amber-500/20" />
                  )}
                  <Icon className={`h-5 w-5 ${cfg.iconClass}`} />
                </button>

                <p
                  className="mt-1.5 max-w-[100px] truncate text-center text-xs text-muted-foreground"
                  title={step.name}
                >
                  {step.name}
                </p>
                <span className={`text-[10px] font-medium ${textColor}`}>
                  {cfg.label}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Workflow detail panel */}
      {selectedAgent && (
        <div className="rounded-xl border border-border bg-card/80 p-5">
          <div className="mb-4 flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              {selectedAgent === "orchestrator" ? (
                <Network className="h-4 w-4 shrink-0 text-primary" />
              ) : selectedStep ? (
                (() => {
                  const cfg = getStepCfg(selectedStep);
                  const Icon = cfg.icon;
                  return (
                    <Icon
                      className={`h-4 w-4 shrink-0 ${cfg.iconClass} ${cfg.color.split(" ").at(-1)}`}
                    />
                  );
                })()
              ) : (
                <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <div>
                <h3 className="text-sm font-semibold text-foreground">
                  {selectedAgent === "orchestrator"
                    ? "Claude Orchestrator"
                    : selectedAgent}
                </h3>
                <p className="text-[11px] text-muted-foreground">
                  {selectedAgent === "orchestrator"
                    ? "Main agent — spawns and coordinates browser subagents"
                    : "Browser-use subagent — scrapes and extracts from the web"}
                </p>
              </div>
            </div>
            <button
              onClick={() => setSelectedAgent(null)}
              className="shrink-0 rounded-full p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto pr-1">
            {selectedAgent === "orchestrator" ? (
              <OrchestratorWorkflow run={run} steps={steps} />
            ) : selectedStep ? (
              <SubagentWorkflow
                step={selectedStep}
                thoughts={findThoughts(selectedAgent)}
              />
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
