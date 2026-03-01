"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { EvidenceArtifact } from "@/lib/types";
import { Copy, Download, Image as ImageIcon, Hash } from "lucide-react";

type EvidenceBundleProps = {
  artifacts: EvidenceArtifact[];
  runId: string;
  timestamp: string;
};

export function EvidenceBundle({
  artifacts,
  runId,
  timestamp,
}: EvidenceBundleProps) {
  const copyHash = (hash: string) => {
    void navigator.clipboard.writeText(hash);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Evidence bundle</CardTitle>
        <p className="text-xs text-muted-foreground">
          Run {runId} · {new Date(timestamp).toLocaleString()}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          {artifacts.map((a) => (
            <div
              key={a.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/30 p-3"
            >
              {a.type === "screenshot" ? (
                <>
                  <div className="flex items-center gap-2">
                    <ImageIcon className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium">{a.label}</span>
                  </div>
                  <div className="h-12 w-20 rounded border border-border bg-muted object-cover" />
                </>
              ) : (
                <>
                  <div className="flex items-center gap-2 min-w-0">
                    <Hash className="h-4 w-4 shrink-0 text-primary" />
                    <span className="truncate text-sm">{a.label}</span>
                  </div>
                  {a.hash && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="shrink-0"
                      onClick={() => copyHash(a.hash!)}
                    >
                      <Copy className="h-3.5 w-3.5" /> Copy
                    </Button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
        <Button variant="outline" className="w-full">
          <Download className="mr-2 h-4 w-4" /> Download evidence bundle
        </Button>
      </CardContent>
    </Card>
  );
}
