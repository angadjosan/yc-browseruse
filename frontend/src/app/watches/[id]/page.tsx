"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import {
  ExternalLink,
  Globe,
  Clock,
  Play,
  Loader2,
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  X,
  Check,
} from "lucide-react";
import { LinearIcon } from "@/components/ui/linear-icon";

function formatInterval(seconds?: number): string {
  if (!seconds) return "daily";
  if (seconds <= 3600) return "Every hour";
  if (seconds <= 86400) return "Every day";
  if (seconds <= 604800) return "Every week";
  return "Every month";
}

export default function WatchDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [running, setRunning] = useState(false);
  const [regStateOpen, setRegStateOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  const {
    data: watch,
    isLoading: watchLoading,
    mutate: mutateWatch,
  } = useSWR(id ? `watch/${id}` : null, () => api.watches.get(id));

  const {
    data: watchRuns = [],
    isLoading: runsLoading,
    mutate: mutateRuns,
  } = useSWR(id ? `watch/${id}/runs` : null, () => api.watches.runs(id), {
    refreshInterval: running ? 3000 : 15_000,
  });

  const { data: changes = [] } = useSWR(
    id ? `watch/${id}/changes` : null,
    () => api.watches.changes(id)
  );

  const handleRunNow = async () => {
    setRunning(true);
    try {
      await api.watches.run(id);
      // Refresh after a short delay to pick up the new run
      setTimeout(() => {
        mutateRuns();
        mutateWatch();
      }, 1500);
    } catch {
      // ignore
    } finally {
      setTimeout(() => setRunning(false), 5000);
    }
  };

  if (watchLoading) {
    return (
      <div className="p-6 md:p-8">
        <p className="text-muted-foreground">Loading watch...</p>
      </div>
    );
  }

  if (!watch) {
    return (
      <div className="p-6 md:p-8">
        <p className="text-destructive">Watch not found.</p>
        <Link
          href="/watches"
          className="mt-2 inline-block text-primary hover:underline"
        >
          Back to watches
        </Link>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-8">
      {/* Back link */}
      <Link
        href="/watches"
        className="text-sm text-muted-foreground hover:text-foreground"
      >
        &larr; Watches
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          {editing ? (
            <div className="space-y-2">
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-lg font-bold text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <textarea
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                rows={2}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                placeholder="Description..."
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={saving}
                  onClick={async () => {
                    setSaving(true);
                    try {
                      await api.watches.update(id, {
                        name: editName,
                        description: editDesc,
                      });
                      await mutateWatch();
                      setEditing(false);
                    } finally {
                      setSaving(false);
                    }
                  }}
                >
                  <Check className="mr-1 h-3.5 w-3.5" />
                  {saving ? "Saving..." : "Save"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditing(false)}
                >
                  <X className="mr-1 h-3.5 w-3.5" />
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <h1 className="text-2xl font-bold text-foreground">{watch.name}</h1>
              {watch.description && (
                <p className="mt-1 text-muted-foreground">{watch.description}</p>
              )}
            </>
          )}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                watch.status === "healthy"
                  ? "bg-primary/20 text-primary"
                  : "bg-warning/20 text-warning"
              }`}
            >
              {watch.status}
            </span>
            {watch.type && watch.type !== "custom" && (
              <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
                {watch.type}
              </span>
            )}
            {watch.jurisdiction && (
              <span className="flex items-center gap-1 rounded-full bg-primary/15 px-2.5 py-0.5 text-xs font-medium text-primary">
                <Globe className="h-3 w-3" />
                {watch.jurisdiction}
              </span>
            )}
            {watch.checkIntervalSeconds && (
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatInterval(watch.checkIntervalSeconds)}
              </span>
            )}
            {watch.nextRunAt && (
              <span className="text-xs text-muted-foreground">
                Next: {new Date(watch.nextRunAt).toLocaleString()}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          {!editing && (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setEditName(watch.name);
                  setEditDesc(watch.description || "");
                  setEditing(true);
                }}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={async () => {
                  if (!window.confirm("Delete this watch? This cannot be undone.")) return;
                  await api.watches.delete(id);
                  router.push("/watches");
                }}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
        <Button onClick={handleRunNow} disabled={running} className="shrink-0">
          {running ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Running...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              Run now
            </>
          )}
        </Button>
      </div>

      {/* Info section */}
      {(watch.riskRationale || watch.sourceUrl) && (
        <section className="rounded-xl border border-border bg-card/80 p-5 space-y-3">
          <h2 className="text-sm font-semibold text-foreground">Risk details</h2>
          {watch.riskRationale && (
            <p className="text-sm text-muted-foreground leading-relaxed">
              {watch.riskRationale}
            </p>
          )}
          {watch.sourceUrl && (
            <a
              href={watch.sourceUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Source URL
            </a>
          )}
        </section>
      )}

      {/* Regulation state */}
      {watch.currentRegulationState && (
        <section className="rounded-xl border border-border bg-card/80">
          <button
            onClick={() => setRegStateOpen(!regStateOpen)}
            className="flex w-full items-center justify-between p-4 text-left"
          >
            <h2 className="text-sm font-semibold text-foreground">
              Current regulation state
            </h2>
            {regStateOpen ? (
              <ChevronDown className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </button>
          {regStateOpen && (
            <div className="border-t border-border p-4">
              <pre className="whitespace-pre-wrap text-xs text-muted-foreground leading-relaxed max-h-96 overflow-auto">
                {watch.currentRegulationState}
              </pre>
            </div>
          )}
        </section>
      )}

      {/* Changes */}
      {changes.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-foreground">
            Alerts ({changes.length})
          </h2>
          <div className="mt-3 space-y-2">
            {changes.map((c) => (
              <Link
                key={c.id}
                href={`/app/run/${c.runId}`}
                className="block rounded-xl border border-border bg-card/80 px-4 py-3 card-hover"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        c.severity === "high"
                          ? "bg-destructive/20 text-destructive"
                          : c.severity === "med"
                          ? "bg-warning/20 text-warning"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {c.severity}
                    </span>
                    <span className="text-sm text-foreground">{c.title}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {c.linearTicketUrl && (
                      <a
                        href={c.linearTicketUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="inline-flex items-center gap-1.5 rounded-md bg-[#5E6AD2]/10 px-2.5 py-1 text-xs font-medium text-[#5E6AD2] transition-colors hover:bg-[#5E6AD2]/20"
                      >
                        <LinearIcon className="h-3 w-3" />
                        Linear
                      </a>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {new Date(c.createdAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                {c.memo && (
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                    {c.memo}
                  </p>
                )}
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Run history */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Run history</h2>
        <div className="mt-3 space-y-2">
          {runsLoading ? (
            <div className="rounded-xl border border-border bg-card/80 p-6 text-center text-muted-foreground">
              Loading runs...
            </div>
          ) : watchRuns.length === 0 ? (
            <div className="rounded-xl border border-border bg-card/80 p-6 text-center text-muted-foreground">
              No runs yet. Click &quot;Run now&quot; to execute this watch.
            </div>
          ) : (
            watchRuns.map((run) => (
              <Link
                key={run.id}
                href={`/app/run/${run.id}`}
                className="block rounded-xl border border-border bg-card/80 px-4 py-3 card-hover"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        run.status === "running"
                          ? "bg-amber-500/20 text-amber-400 animate-pulse"
                          : run.status === "failed"
                          ? "bg-destructive/20 text-destructive"
                          : "bg-primary/20 text-primary"
                      }`}
                    >
                      {run.status ?? "completed"}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {new Date(run.startedAt).toLocaleString()}
                    </span>
                    {run.selfHealed && (
                      <span className="rounded-full bg-primary/20 px-2 py-0.5 text-xs text-primary">
                        Self-healed
                      </span>
                    )}
                  </div>
                  <span className="text-sm text-muted-foreground">
                    View run detail &rarr;
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
