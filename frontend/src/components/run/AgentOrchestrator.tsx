"use client";

import { useState, useEffect, useRef } from "react";
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
  Timer,
  Activity,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

type Props = {
  run: Run;
  isStreaming?: boolean;
};

const statusConfig = {
  running: {
    color: "border-amber-500 bg-amber-500/10 text-amber-400",
    ring: "ring-amber-500/30",
    icon: Loader2,
    iconClass: "animate-spin",
    label: "Running",
    dot: "bg-amber-400",
  },
  done: {
    color: "border-emerald-500 bg-emerald-500/10 text-emerald-400",
    ring: "ring-emerald-500/30",
    icon: CheckCircle2,
    iconClass: "",
    label: "Done",
    dot: "bg-emerald-400",
  },
  retry: {
    color: "border-red-500 bg-red-500/10 text-red-400",
    ring: "ring-red-500/30",
    icon: RefreshCw,
    iconClass: "",
    label: "Retry",
    dot: "bg-red-400",
  },
  pending: {
    color: "border-zinc-600 bg-zinc-800/50 text-zinc-500",
    ring: "ring-zinc-600/30",
    icon: Clock,
    iconClass: "",
    label: "Pending",
    dot: "bg-zinc-500",
  },
} as const;

function getStepCfg(step: RunStep) {
  const s = step.status as keyof typeof statusConfig;
  return statusConfig[s] ?? statusConfig.pending;
}

function dedupeSteps(steps: RunStep[]): RunStep[] {
  const map = new Map<string, RunStep>();
  for (const step of steps) {
    map.set(step.name, step);
  }
  return Array.from(map.values());
}

// ── Elapsed timer ─────────────────────────────────────────────────────────────

function ElapsedTimer({
  startedAt,
  endedAt,
  isRunning,
}: {
  startedAt: string;
  endedAt?: string;
  isRunning: boolean;
}) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  const start = new Date(startedAt).getTime();
  if (isNaN(start)) return <span className="tabular-nums">--:--</span>;
  const end = endedAt && !isRunning ? new Date(endedAt).getTime() : now;
  const elapsed = Math.max(0, Math.floor((end - start) / 1000));
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;

  return (
    <span className="tabular-nums">
      {m}:{s.toString().padStart(2, "0")}
    </span>
  );
}

// ── Stats bar ─────────────────────────────────────────────────────────────────

function StatsBar({
  run,
  steps,
  isStreaming,
}: {
  run: Run;
  steps: RunStep[];
  isStreaming: boolean;
}) {
  const isRunning = run.status === "running";
  const doneCount = steps.filter((s) => s.status === "done").length;
  const total = steps.length;
  const pct = total > 0 ? (doneCount / total) * 100 : 0;

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card/80 px-5 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15">
            <Activity className="h-4 w-4 text-primary" />
          </div>
          <div>
            <span className="text-sm font-semibold text-foreground">
              Agent Orchestrator
            </span>
            <p className="text-[11px] text-muted-foreground">
              {isRunning
                ? `${steps.filter((s) => s.status === "running").length} active · ${doneCount} done`
                : run.status === "failed"
                  ? `${doneCount} of ${total} completed before failure`
                  : `${doneCount} of ${total} agents completed`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {isStreaming && (
            <span className="flex items-center gap-1.5 rounded-full border border-primary/20 bg-primary/10 px-2.5 py-1 text-[10px] font-medium text-primary">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-primary" />
              Live
            </span>
          )}
          {!isStreaming && isRunning && (
            <span className="flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-muted-foreground" />
              Polling
            </span>
          )}
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Timer className="h-3.5 w-3.5" />
            <ElapsedTimer
              startedAt={run.startedAt}
              endedAt={run.endedAt}
              isRunning={isRunning}
            />
          </div>
        </div>
      </div>

      {total > 0 && (
        <div className="flex items-center gap-3">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="shrink-0 text-[11px] tabular-nums text-muted-foreground">
            {doneCount}/{total}
          </span>
        </div>
      )}
    </div>
  );
}

// ── Orchestrator detail panel ─────────────────────────────────────────────────

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
                <Icon
                  className={`h-3.5 w-3.5 ${cfg.iconClass} ${textColor}`}
                />
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
          <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/80">
            {run.agentSummary}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Subagent detail panel ─────────────────────────────────────────────────────

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
            <div
              key={i}
              className="flex gap-3 border-l-2 border-primary/30 pl-3"
            >
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

// ── Live Activity Feed ────────────────────────────────────────────────────────

function LiveActivityFeed({
  steps,
  isRunning,
}: {
  steps: RunStep[];
  isRunning: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    if (scrollRef.current && expanded) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [steps.length, expanded]);

  if (steps.length === 0 && !isRunning) return null;

  return (
    <div className="rounded-xl border border-border bg-[#080c0a] overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-muted/30"
      >
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-primary" />
          <span className="text-xs font-medium text-foreground">
            Activity Log
          </span>
          <span className="text-[10px] text-muted-foreground">
            {steps.length} event{steps.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isRunning && (
            <span className="flex items-center gap-1 text-[10px] text-amber-400">
              <span className="live-dot h-1 w-1 rounded-full bg-amber-400" />
              streaming
            </span>
          )}
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>

      {expanded && (
        <div
          ref={scrollRef}
          className="max-h-56 overflow-y-auto border-t border-border/50 px-4 py-2 font-mono text-[11px]"
        >
          {steps.length === 0 ? (
            <p className="py-3 text-center text-muted-foreground/60">
              Waiting for agent activity…
              <span className="terminal-cursor ml-1">▊</span>
            </p>
          ) : (
            <div className="space-y-0.5">
              {steps.map((step, i) => {
                const cfg = getStepCfg(step);
                const textColor = cfg.color.split(" ").at(-1)!;
                const time = step.timestamp
                  ? new Date(step.timestamp).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      second: "2-digit",
                    })
                  : "--:--:--";

                return (
                  <div
                    key={`${step.name}-${step.status}-${i}`}
                    className="feed-line flex items-baseline gap-3 rounded px-1 py-0.5 hover:bg-white/[0.02]"
                  >
                    <span className="shrink-0 text-muted-foreground/40 tabular-nums">
                      {time}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-foreground/80">
                      {step.name}
                    </span>
                    <span
                      className={`shrink-0 flex items-center gap-1 ${textColor}`}
                    >
                      <span
                        className={`inline-block h-1.5 w-1.5 rounded-full ${cfg.dot} ${step.status === "running" ? "animate-pulse" : ""}`}
                      />
                      {cfg.label.toLowerCase()}
                    </span>
                  </div>
                );
              })}
              {isRunning && (
                <div className="flex items-center gap-1 px-1 py-1 text-muted-foreground/40">
                  <span className="terminal-cursor">▊</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function AgentOrchestrator({ run, isStreaming = false }: Props) {
  const [selectedAgent, setSelectedAgent] = useState<
    "orchestrator" | string | null
  >(null);

  const isRunning = run.status === "running";
  const uniqueSteps = dedupeSteps(run.steps ?? []);
  const thoughts = run.agentThoughts ?? [];

  // Auto-select the first running agent if nothing is selected
  useEffect(() => {
    if (selectedAgent !== null) return;
    if (!isRunning) return;
    const firstRunning = uniqueSteps.find((s) => s.status === "running");
    if (firstRunning) {
      setSelectedAgent(firstRunning.name);
    }
  }, [uniqueSteps, isRunning, selectedAgent]);

  function findThoughts(stepName: string): AgentThought | undefined {
    return thoughts.find(
      (t) =>
        t.target_name === stepName ||
        stepName.startsWith(t.target_name?.slice(0, 20) ?? "")
    );
  }

  const activeCount = uniqueSteps.filter(
    (s) => s.status === "running"
  ).length;
  const doneCount = uniqueSteps.filter((s) => s.status === "done").length;

  const selectedStep =
    selectedAgent && selectedAgent !== "orchestrator"
      ? uniqueSteps.find((s) => s.name === selectedAgent) ?? null
      : null;

  return (
    <div className="space-y-6">
      {/* Stats bar */}
      <StatsBar run={run} steps={uniqueSteps} isStreaming={isStreaming} />

      {/* Agent graph */}
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
                : run.status === "failed"
                  ? "border-red-500 bg-red-500/10 text-red-400"
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
              : run.status === "failed"
                ? `Failed after ${doneCount} agent${doneCount !== 1 ? "s" : ""}`
                : `Completed ${doneCount} agent${doneCount !== 1 ? "s" : ""}`}
          </p>
        </div>

        {/* Connector line */}
        {uniqueSteps.length > 0 && (
          <div className="flex justify-center">
            <div className="h-8 w-px bg-border" />
          </div>
        )}

        {/* Subagent nodes */}
        {uniqueSteps.length > 0 && (
          <div className="flex flex-wrap justify-center gap-5">
            {uniqueSteps.map((step, i) => {
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
                    className={`group relative flex h-16 w-16 items-center justify-center rounded-full border-2 transition-all hover:ring-2 ${cfg.color} ${cfg.ring} ${isSelected ? "ring-2" : ""}`}
                  >
                    {step.status === "running" && (
                      <div className="absolute inset-0 animate-ping rounded-full border border-amber-500/20" />
                    )}
                    <Icon className={`h-5 w-5 ${cfg.iconClass}`} />
                  </button>

                  <p
                    className="mt-1.5 max-w-[160px] truncate text-center text-xs text-muted-foreground"
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
      </div>

      {/* Detail panel */}
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
              <OrchestratorWorkflow run={run} steps={uniqueSteps} />
            ) : selectedStep ? (
              <SubagentWorkflow
                step={selectedStep}
                thoughts={findThoughts(selectedAgent)}
              />
            ) : null}
          </div>
        </div>
      )}

      {/* Live activity feed */}
      <LiveActivityFeed steps={run.steps ?? []} isRunning={isRunning} />
    </div>
  );
}
