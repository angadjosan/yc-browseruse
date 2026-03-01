"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChangeEvent } from "@/lib/types";
import { motion } from "framer-motion";
import { ExternalLink } from "lucide-react";

type ChangesCardProps = {
  activeJurisdiction: string | null;
  changes: ChangeEvent[];
  setChanges?: (c: ChangeEvent[]) => void;
};

const severityVariant = { low: "low", med: "med", high: "high" } as const;

export function ChangesCard({
  activeJurisdiction,
  changes,
}: ChangesCardProps) {
  const filtered = activeJurisdiction
    ? changes.filter((c) => c.jurisdiction === activeJurisdiction)
    : changes;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.05 }}
    >
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">Latest Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {filtered.slice(0, 5).map((c) => (
              <li key={c.id}>
                <Link
                  href={`/app/run/${c.runId}`}
                  className="block rounded-lg border border-border bg-muted/30 p-3 transition-colors hover:border-primary/30 hover:bg-muted/50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-foreground">
                        {c.title}
                      </p>
                      <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                        {c.memo}
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Badge variant={severityVariant[c.severity]}>
                          {c.severity}
                        </Badge>
                        <Badge variant="secondary">{c.jurisdiction}</Badge>
                        <span className="text-xs text-muted-foreground">
                          {new Date(c.createdAt).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <Button size="sm" variant="ghost" className="shrink-0" asChild>
                      <span>
                        <ExternalLink className="h-3.5 w-3.5" /> Open
                      </span>
                    </Button>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <Link
            href="/alerts"
            className="mt-3 block text-center text-xs font-medium text-primary hover:underline"
          >
            View all alerts &rarr;
          </Link>
        </CardContent>
      </Card>
    </motion.div>
  );
}
