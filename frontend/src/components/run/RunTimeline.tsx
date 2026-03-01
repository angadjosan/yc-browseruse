"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { RunStep } from "@/lib/types";
import { Check, Circle, RefreshCw } from "lucide-react";

type RunTimelineProps = {
  steps: RunStep[];
};

export function RunTimeline({ steps }: RunTimelineProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Run timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {steps.map((step, i) => (
            <li key={i} className="flex items-center gap-3">
              <span
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border ${
                  step.status === "done" || step.status === "retry"
                    ? "border-primary bg-primary/20 text-primary"
                    : step.status === "running"
                      ? "border-primary bg-primary/10 text-primary animate-pulse"
                      : "border-border bg-muted text-muted-foreground"
                }`}
              >
                {step.status === "retry" ? (
                  <RefreshCw className="h-4 w-4" />
                ) : step.status === "done" ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <Circle className="h-3 w-3" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-foreground">
                  {step.name}
                  {step.status === "retry" && (
                    <Badge variant="healthy" className="ml-2">Self-healed</Badge>
                  )}
                </p>
                {step.timestamp && (
                  <p className="text-xs text-muted-foreground">
                    {step.timestamp}
                  </p>
                )}
              </div>
              <Badge
                variant={
                  step.status === "done" || step.status === "retry"
                    ? "healthy"
                    : step.status === "running"
                      ? "secondary"
                      : "outline"
                }
              >
                {step.status}
              </Badge>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
