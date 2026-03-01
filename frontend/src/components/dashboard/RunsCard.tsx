"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { motion, AnimatePresence } from "framer-motion";

type RunStep = {
  name: string;
  status: "pending" | "running" | "done" | "retry";
};

type RunsCardProps = {
  currentRunSteps: RunStep[] | null;
  isRunning: boolean;
  lastFailureSummary: string | null;
  completionRate: number;
  falsePositiveRate: number;
};

export function RunsCard({
  currentRunSteps,
  isRunning,
  lastFailureSummary,
  completionRate,
  falsePositiveRate,
}: RunsCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">Runs / Reliability</CardTitle>
          {currentRunSteps?.some((s) => s.status === "retry") && (
            <Badge variant="healthy">Self-healed</Badge>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {currentRunSteps && currentRunSteps.length > 0 ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground">
                {isRunning ? "Current run" : "Last run"}
              </p>
              <div className="flex flex-wrap gap-2">
                <AnimatePresence mode="wait">
                  {currentRunSteps.map((step) => (
                    <motion.span
                      key={step.name}
                      initial={{ opacity: 0, scale: 0.9 }}
                      animate={{ opacity: 1, scale: 1 }}
                      className={`inline-flex items-center rounded-md px-2 py-1 text-xs ${
                        step.status === "done" || step.status === "retry"
                          ? "bg-primary/20 text-primary"
                          : step.status === "running"
                            ? "bg-primary/10 text-primary animate-pulse"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {step.status === "retry" && "↻ "}
                      {step.name}
                    </motion.span>
                  ))}
                </AnimatePresence>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No run in progress. Use &quot;Run all&quot; to start a sweep.
            </p>
          )}

          {lastFailureSummary && (
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <p className="text-xs font-medium text-muted-foreground">
                Last failure
              </p>
              <p className="mt-1 text-sm text-foreground">{lastFailureSummary}</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 text-center">
            <div>
              <p className="text-2xl font-semibold text-primary">
                {completionRate}%
              </p>
              <p className="text-xs text-muted-foreground">Completion rate</p>
            </div>
            <div>
              <p className="text-2xl font-semibold text-foreground">
                {falsePositiveRate}%
              </p>
              <p className="text-xs text-muted-foreground">False positive rate</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
