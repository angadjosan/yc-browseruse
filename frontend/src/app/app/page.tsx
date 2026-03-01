"use client";

import * as React from "react";
import { CommandBar } from "@/components/dashboard/CommandBar";
import { WatchesCard } from "@/components/dashboard/WatchesCard";
import { ChangesCard } from "@/components/dashboard/ChangesCard";
import { RunsCard } from "@/components/dashboard/RunsCard";
import { JurisdictionGlobe } from "@/components/dashboard/JurisdictionGlobe";
import {
  changeEvents,
  globePoints,
} from "@/lib/mockData";
import type { ChangeEvent, RunStep } from "@/lib/types";
import { LayoutDashboard, Radar } from "lucide-react";

const RUN_STEP_NAMES: RunStep["name"][] = [
  "Searching",
  "Navigating",
  "Capturing",
  "Hashing",
  "Diffing",
  "Ticketing",
  "Done",
];

export default function DashboardPage() {
  const [activeJurisdiction, setActiveJurisdiction] = React.useState<
    string | null
  >(null);
  const [changes, setChanges] = React.useState<ChangeEvent[]>(changeEvents);
  const [currentRunSteps, setCurrentRunSteps] = React.useState<RunStep[] | null>(
    null
  );
  const [isRunning, setIsRunning] = React.useState(false);

  const runAll = React.useCallback(() => {
    if (isRunning) return;
    setIsRunning(true);
    const withRetry = Math.random() > 0.5;
    const steps: RunStep[] = RUN_STEP_NAMES.map((name) => ({ name, status: "pending" }));
    setCurrentRunSteps(steps);

    let stepIndex = 0;
    const advance = () => {
      if (stepIndex >= steps.length) {
        setIsRunning(false);
        setChanges((prev) => [
          {
            id: `c-new-${Date.now()}`,
            watchId: "w1",
            title: "GDPR guidance for AI profiling",
            memo: "Simulated change detected from Run all.",
            severity: "med",
            jurisdiction: "EU",
            sourceType: "regulator",
            createdAt: new Date().toISOString(),
            runId: `r-${Date.now()}`,
          },
          ...prev,
        ]);
        return;
      }
      setCurrentRunSteps((prev) => {
        if (!prev) return prev;
        const next = prev.map((s, i) =>
          i === stepIndex
            ? { ...s, status: "running" as const }
            : i < stepIndex
              ? { ...s, status: "done" as const }
              : s
        );
        return next;
      });
      setTimeout(() => {
        setCurrentRunSteps((prev) => {
          if (!prev) return prev;
          const next = prev.map((s, i) =>
            i === stepIndex ? { ...s, status: "done" as const } : s
          );
          if (withRetry && stepIndex === 2) {
            next[2] = { ...next[2], status: "retry" };
            return next;
          }
          return next;
        });
        if (withRetry && stepIndex === 2) {
          setTimeout(() => {
            stepIndex++;
            setTimeout(advance, 400);
          }, 600);
        } else {
          stepIndex++;
          setTimeout(advance, 800);
        }
      }, 800);
    };
    advance();
  }, [isRunning]);

  return (
    <div className="relative min-h-screen">
      {/* Subtle gradient background (green nighty night) */}
      <div
        className="pointer-events-none fixed inset-0 z-0"
        aria-hidden
      >
        <div
          className="absolute inset-0 opacity-30"
          style={{
            background:
              "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,255,136,0.12), transparent 50%), radial-gradient(ellipse 60% 40% at 100% 50%, rgba(0,255,136,0.06), transparent 40%)",
          }}
        />
      </div>

      <div className="relative z-10 space-y-8 p-6 md:p-8">
        {/* Header */}
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

        <CommandBar />

        {/* Cards grid */}
        <div className="grid gap-6 md:grid-cols-3">
          <WatchesCard
            activeJurisdiction={activeJurisdiction}
            onRunAll={runAll}
          />
          <ChangesCard
            activeJurisdiction={activeJurisdiction}
            changes={changes}
            setChanges={setChanges}
          />
          <RunsCard
            currentRunSteps={currentRunSteps}
            isRunning={isRunning}
            lastFailureSummary={null}
            completionRate={98}
            falsePositiveRate={2}
          />
        </div>

        {/* Jurisdiction Radar - centered, prominent */}
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
