"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DiffData } from "@/lib/types";

type DiffViewerProps = {
  diff: DiffData;
  impactMemo?: string[];
};

export function DiffViewer({ diff, impactMemo }: DiffViewerProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Diff viewer</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Before
          </p>
          <pre className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-foreground whitespace-pre-wrap">
            {diff.before}
          </pre>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            After
          </p>
          <pre className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-foreground whitespace-pre-wrap">
            {diff.after}
          </pre>
        </div>
        {diff.highlights?.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Highlights
            </p>
            <ul className="space-y-1">
              {diff.highlights.map((h, i) => (
                <li
                  key={i}
                  className={`rounded px-2 py-1 text-xs ${
                    h.type === "add"
                      ? "border-l-2 border-primary bg-primary/10 text-primary"
                      : h.type === "remove"
                        ? "border-l-2 border-destructive bg-destructive/10 text-destructive"
                        : "border-l-2 border-border text-muted-foreground"
                  }`}
                >
                  {h.text}
                </li>
              ))}
            </ul>
          </div>
        )}
        {impactMemo && impactMemo.length > 0 && (
          <div>
            <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Impact memo
            </p>
            <ul className="list-inside list-disc space-y-0.5 text-sm text-foreground">
              {impactMemo.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
