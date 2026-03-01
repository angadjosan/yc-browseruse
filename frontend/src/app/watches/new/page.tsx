"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";

const SCHEDULE_OPTIONS: { label: string; cron: string }[] = [
  { label: "Hourly", cron: "0 * * * *" },
  { label: "Daily", cron: "0 9 * * *" },
  { label: "Weekly", cron: "0 9 * * 1" },
  { label: "Monthly", cron: "0 9 1 * *" },
];

const inputClass =
  "mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:border-[var(--primary)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]";

export default function NewWatchPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("regulation");
  const [targetUrl, setTargetUrl] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [extractionInstructions, setExtractionInstructions] = useState("");
  const [schedule, setSchedule] = useState("0 9 * * *");
  const [linearTeamId, setLinearTeamId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const integrations: Record<string, string> = {};
      if (linearTeamId.trim()) integrations.linear_team_id = linearTeamId.trim();

      const watch = await api.watches.create({
        name,
        description: description || undefined,
        type,
        config: {
          targets: [
            {
              name: name || "Default target",
              starting_url: targetUrl || undefined,
              search_query: searchQuery || name,
              extraction_instructions:
                extractionInstructions ||
                "Extract the main regulatory or policy text.",
            },
          ],
        },
        integrations: Object.keys(integrations).length > 0 ? integrations : undefined,
        schedule: { cron: schedule },
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
      <Link
        href="/watches"
        className="text-sm text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
      >
        &larr; Back to watches
      </Link>
      <h1 className="mt-4 text-2xl font-bold text-[var(--foreground)]">
        New watch
      </h1>
      <p className="mt-1 text-[var(--muted-foreground)]">
        Create a watch to monitor a regulation, vendor policy, or custom target.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-6">
        {error && (
          <div className="rounded-lg border border-[var(--destructive)]/50 bg-[var(--destructive)]/10 px-4 py-3 text-sm text-[var(--destructive)]">
            {error}
          </div>
        )}

        {/* Name */}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-[var(--foreground)]">
            Name <span className="text-destructive">*</span>
          </label>
          <input
            id="name"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={inputClass}
            placeholder="e.g. GDPR Article 25"
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-[var(--foreground)]">
            Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={3}
            className={inputClass}
            placeholder="What this watch monitors and why."
          />
        </div>

        {/* Type */}
        <div>
          <label htmlFor="type" className="block text-sm font-medium text-[var(--foreground)]">
            Type
          </label>
          <select
            id="type"
            value={type}
            onChange={(e) => setType(e.target.value)}
            className={inputClass}
          >
            <option value="regulation">Regulation</option>
            <option value="vendor">Vendor policy</option>
            <option value="internal">Internal policy</option>
            <option value="custom">Custom</option>
          </select>
        </div>

        {/* Target URL */}
        <div>
          <label htmlFor="targetUrl" className="block text-sm font-medium text-[var(--foreground)]">
            Target URL
          </label>
          <input
            id="targetUrl"
            type="url"
            value={targetUrl}
            onChange={(e) => setTargetUrl(e.target.value)}
            className={inputClass}
            placeholder="https://gdpr-info.eu/art-25-gdpr/"
          />
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            The starting URL for the browser agent to scrape.
          </p>
        </div>

        {/* Search query */}
        <div>
          <label htmlFor="searchQuery" className="block text-sm font-medium text-[var(--foreground)]">
            Search query
          </label>
          <input
            id="searchQuery"
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={inputClass}
            placeholder="GDPR Article 25 data protection by design"
          />
          <p className="mt-1 text-xs text-[var(--muted-foreground)]">
            Search terms the agent uses to find the regulation text. Defaults to the watch name.
          </p>
        </div>

        {/* Extraction instructions */}
        <div>
          <label htmlFor="extraction" className="block text-sm font-medium text-[var(--foreground)]">
            Extraction instructions
          </label>
          <textarea
            id="extraction"
            value={extractionInstructions}
            onChange={(e) => setExtractionInstructions(e.target.value)}
            rows={3}
            className={inputClass}
            placeholder="Extract the full text of the regulation article, including any sub-sections."
          />
        </div>

        {/* Schedule */}
        <div>
          <label htmlFor="schedule" className="block text-sm font-medium text-[var(--foreground)]">
            Check schedule
          </label>
          <select
            id="schedule"
            value={schedule}
            onChange={(e) => setSchedule(e.target.value)}
            className={inputClass}
          >
            {SCHEDULE_OPTIONS.map((opt) => (
              <option key={opt.cron} value={opt.cron}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Integrations */}
        <fieldset className="space-y-4 rounded-lg border border-[var(--border)] p-4">
          <legend className="px-2 text-sm font-medium text-[var(--foreground)]">
            Integrations (optional)
          </legend>
          <div>
            <label htmlFor="linear" className="block text-sm text-[var(--muted-foreground)]">
              Linear team ID
            </label>
            <input
              id="linear"
              type="text"
              value={linearTeamId}
              onChange={(e) => setLinearTeamId(e.target.value)}
              className={inputClass}
              placeholder="e.g. TEAM-123"
            />
          </div>
        </fieldset>

        <div className="flex gap-3 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? "Creating..." : "Create watch"}
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
