"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { createWatch } from "@/lib/api";

export default function NewWatchPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("custom");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const watch = await createWatch({
        name,
        description: description || undefined,
        type,
        config: {
          targets: [
            {
              name: name || "Default target",
              description: description || name,
              search_query: name,
              extraction_instructions: "Extract the main regulatory or policy text.",
            },
          ],
          schedule: { cron: "0 9 * * *", timezone: "UTC" },
        },
      });
      router.push(`/watches/${watch.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create watch");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="p-8 max-w-2xl">
      <Link href="/watches" className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]">
        ← Back to watches
      </Link>
      <h1 className="mt-4 text-2xl font-bold text-[var(--foreground)]">New watch</h1>
      <p className="mt-1 text-[var(--muted-foreground)]">
        Create a watch to monitor a regulation, vendor policy, or custom target.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        {error && (
          <div className="rounded-lg border border-[var(--destructive)]/50 bg-[var(--destructive)]/10 px-4 py-3 text-sm text-[var(--destructive)]">
            {error}
          </div>
        )}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-[var(--foreground)]">
            Name
          </label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            placeholder="e.g. GDPR Article 25"
          />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-[var(--foreground)]">
            Description (optional)
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
            placeholder="What this watch monitors and why."
          />
        </div>
        <div>
          <label htmlFor="type" className="block text-sm font-medium text-[var(--foreground)]">
            Type
          </label>
          <select
            id="type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
          >
            <option value="regulation">Regulation</option>
            <option value="vendor">Vendor policy</option>
            <option value="internal">Internal policy</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? "Creating…" : "Create watch"}
          </button>
          <Link
            href="/watches"
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--muted)] transition-colors"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
