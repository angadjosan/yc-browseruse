"use client";

import * as React from "react";
import useSWR from "swr";
import { CommandBar } from "@/components/dashboard/CommandBar";
import { WatchesCard } from "@/components/dashboard/WatchesCard";
import { ChangesCard } from "@/components/dashboard/ChangesCard";
import { RunsCard } from "@/components/dashboard/RunsCard";
import { JurisdictionGlobe } from "@/components/dashboard/JurisdictionGlobe";
import { api } from "@/lib/api";
import type { RunStep } from "@/lib/types";
import { LayoutDashboard, Radar } from "lucide-react";

const RUN_STEP_NAMES: string[] = [
  "Searching",
  "Navigating",
  "Capturing",
  "Hashing",
  "Diffing",
  "Ticketing",
];

export default function DashboardPage() {
  const [activeJurisdiction, setActiveJurisdiction] = React.useState<string | null>(null);
  const [currentRunSteps, setCurrentRunSteps] = React.useState<RunStep[] | null>(null);
  const [isRunning, setIsRunning] = React.useState(false);

  const { data: watches = [], mutate: mutateWatches } = useSWR("watches", api.watches.list, {
    refreshInterval: 30_000,
  });
  const { data: changes = [], mutate: mutateChanges } = useSWR("changes", () =>
    api.changes.list(20)
  );
  const { data: globePoints = [] } = useSWR("globe", api.globe.points, {
    refreshInterval: 60_000,
  });
  const { data: recentRuns = [] } = useSWR("runs/recent", api.runs.recent, {
    refreshInterval: 30_000,
  });

  const completionRate = recentRuns.length
    ? Math.round(
        (recentRuns.filter((r) => !r.selfHealed).length / recentRuns.length) * 100
      )
    : 98;
  const falsePositiveRate = recentRuns.length
    ? Math.round(
        (recentRuns.filter((r) => r.selfHealed).length / recentRuns.length) * 100
      )
    : 2;

  const runAll = React.useCallback(async () => {
    if (isRunning || watches.length === 0) return;
    setIsRunning(true);
    setCurrentRunSteps(
      RUN_STEP_NAMES.map((name) => ({ name, status: "pending" as const }))
    );

    try {
      const { run_id } = await api.watches.run(watches[0].id);

      const poll = setInterval(async () => {
        try {
          const run = await api.runs.get(run_id);
          setCurrentRunSteps(run.steps);
          if (run.endedAt && run.endedAt !== run.startedAt) {
            clearInterval(poll);
            setIsRunning(false);
            mutateChanges();
            mutateWatches();
          }
        } catch {
          clearInterval(poll);
          setIsRunning(false);
        }
      }, 2000);
    } catch {
      setIsRunning(false);
      setCurrentRunSteps(null);
    }
  }, [isRunning, watches, mutateChanges, mutateWatches]);

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 z-0" aria-hidden>
        <div
          className="absolute inset-0 opacity-30"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,255,136,0.12), transparent 50%), radial-gradient(ellipse 60% 40% at 100% 50%, rgba(0,255,136,0.06), transparent 40%)",
          }}
        />
      </div>

      <div className="relative z-10 space-y-8 p-6 md:p-8">
        <header className="flex flex-col gap-1">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary shadow-[0_0_20px_-4px_rgba(0,255,136,0.3)]">
              <LayoutDashboard className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                Dashboard
              </h1>
              <p className="text-sm text-muted-foreground">
                Mission control for compliance watches and change detection
              </p>
            </div>
          </div>
        </header>

        <CommandBar
          onWatchesCreated={() => {
            mutateWatches();
            mutateChanges();
          }}
        />

        <div className="grid gap-6 md:grid-cols-3">
          <WatchesCard
            watches={watches}
            activeJurisdiction={activeJurisdiction}
            onRunAll={runAll}
          />
          <ChangesCard
            activeJurisdiction={activeJurisdiction}
            changes={changes}
          />
          <RunsCard
            currentRunSteps={currentRunSteps}
            isRunning={isRunning}
            lastFailureSummary={null}
            completionRate={completionRate}
            falsePositiveRate={falsePositiveRate}
          />
        </div>

        <section className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Radar className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium">Global coverage</span>
          </div>
          <JurisdictionGlobe
            points={globePoints}
            activeJurisdiction={activeJurisdiction}
            onSelectJurisdiction={setActiveJurisdiction}
          />
        </section>
      </div>
    </div>
  );
}
