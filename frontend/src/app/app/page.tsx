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
    <div className="space-y-8 p-6 md:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Mission control for your compliance watches and change detection.
        </p>
      </div>

      <CommandBar />

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
          lastFailureSummary={
            null
          }
          completionRate={98}
          falsePositiveRate={2}
        />
      </div>

      <JurisdictionGlobe
        points={globePoints}
        activeJurisdiction={activeJurisdiction}
        onSelectJurisdiction={setActiveJurisdiction}
      />
    </div>
  );
}
