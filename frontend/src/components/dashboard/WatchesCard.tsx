"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Watch } from "@/lib/types";
import { Play, Plus } from "lucide-react";
import { motion } from "framer-motion";

type WatchesCardProps = {
  activeJurisdiction: string | null;
  onRunAll: () => void;
  watches?: Watch[];
};

export function WatchesCard({ activeJurisdiction, onRunAll, watches: watchesProp }: WatchesCardProps) {
  const allWatches = watchesProp ?? [];
  const watches = activeJurisdiction
    ? allWatches.filter((w) => w.jurisdictions.includes(activeJurisdiction))
    : allWatches;

  const healthy = watches.filter((w) => w.status === "healthy").length;
  const degraded = watches.filter((w) => w.status === "degraded").length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">Watches</CardTitle>
          <div className="flex gap-1.5">
            <Badge variant="healthy">{healthy} Healthy</Badge>
            {degraded > 0 && <Badge variant="degraded">{degraded} Degraded</Badge>}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {watches.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No watches yet.{" "}
              <Link href="/watches/new" className="text-primary hover:underline">
                Create one
              </Link>{" "}
              to start monitoring.
            </p>
          ) : (
            <ul className="space-y-2">
              {watches.slice(0, 5).map((w) => (
                <li key={w.id} className="flex items-center justify-between gap-2 text-sm">
                  <div className="min-w-0 flex-1">
                    <Link href={`/watches/${w.id}`} className="truncate font-medium text-foreground hover:text-primary transition-colors">
                      {w.name}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      Next: {w.nextRunAt ? new Date(w.nextRunAt).toLocaleDateString() : "—"} · Last:{" "}
                      {w.lastRunAt ? new Date(w.lastRunAt).toLocaleDateString() : "—"}
                    </p>
                  </div>
                  <Badge variant={w.status === "healthy" ? "healthy" : "degraded"}>
                    {w.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          {watches.length > 5 && (
            <Link
              href="/watches"
              className="block text-center text-xs font-medium text-primary hover:underline"
            >
              View all watches &rarr;
            </Link>
          )}
          <div className="flex gap-2">
            <Button size="sm" onClick={onRunAll} className="flex-1" disabled={watches.length === 0}>
              <Play className="mr-1.5 h-3.5 w-3.5" /> Run all
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link href="/watches/new">
                <Plus className="mr-1.5 h-3.5 w-3.5" /> New watch
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
