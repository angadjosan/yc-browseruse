"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { api } from "@/lib/api";
import { Pencil, Trash2, Check, X } from "lucide-react";

export default function WatchesPage() {
  const router = useRouter();
  const { data: watches = [], isLoading, mutate } = useSWR("watches", api.watches.list, {
    refreshInterval: 30_000,
  });
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [saving, setSaving] = useState(false);

  return (
    <div className="p-6 md:p-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Watches</h1>
          <p className="mt-1 text-muted-foreground">
            Manage compliance watches. Each watch monitors targets and runs on a schedule.
          </p>
        </div>
        <Link
          href="/watches/new"
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity shrink-0"
        >
          New watch
        </Link>
      </div>

      <div className="mt-8 space-y-3">
        {isLoading ? (
          <div className="rounded-xl border border-border bg-card/80 p-8 text-center text-muted-foreground">
            Loading watches…
          </div>
        ) : watches.length === 0 ? (
          <div className="rounded-xl border border-border border-dashed bg-card/80 p-12 text-center text-muted-foreground">
            No watches. Create one to monitor regulations or vendor policies.{" "}
            <Link href="/watches/new" className="text-primary hover:underline">
              Create watch
            </Link>
          </div>
        ) : (
          watches.map((w) => (
            <div
              key={w.id}
              className="rounded-xl border border-border bg-card/80 p-5 card-hover"
            >
              {editingId === w.id ? (
                <div className="space-y-2">
                  <input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <input
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    placeholder="Description..."
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <div className="flex gap-2">
                    <button
                      disabled={saving}
                      onClick={async () => {
                        setSaving(true);
                        try {
                          await api.watches.update(w.id, { name: editName, description: editDesc });
                          await mutate();
                          setEditingId(null);
                        } finally {
                          setSaving(false);
                        }
                      }}
                      className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity"
                    >
                      <Check className="h-3.5 w-3.5" />
                      {saving ? "Saving…" : "Save"}
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted transition-colors"
                    >
                      <X className="h-3.5 w-3.5" />
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <Link href={`/watches/${w.id}`} className="min-w-0 flex-1">
                    <p className="font-medium text-foreground">{w.name}</p>
                    <p className="mt-0.5 text-sm text-muted-foreground">{w.description}</p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {w.nextRunAt
                        ? `Next run: ${new Date(w.nextRunAt).toLocaleString()}`
                        : "No next run scheduled"}
                      {w.lastRunAt && ` · Last: ${new Date(w.lastRunAt).toLocaleString()}`}
                    </p>
                  </Link>
                  <div className="flex items-center gap-2 shrink-0 ml-4">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        w.status === "healthy"
                          ? "bg-primary/20 text-primary"
                          : "bg-warning/20 text-warning"
                      }`}
                    >
                      {w.status}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditName(w.name);
                        setEditDesc(w.description || "");
                        setEditingId(w.id);
                      }}
                      className="rounded-lg border border-border p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
                      title="Edit watch"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        if (!window.confirm(`Delete "${w.name}"? This cannot be undone.`)) return;
                        await api.watches.delete(w.id);
                        mutate();
                      }}
                      className="rounded-lg border border-destructive/30 p-1.5 text-destructive hover:bg-destructive/10 transition-colors"
                      title="Delete watch"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
