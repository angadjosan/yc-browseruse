const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Watch = {
  id: string;
  name: string;
  description: string | null;
  status: string;
  next_run_at: string | null;
  total_runs: number;
  total_changes: number;
  config?: Record<string, unknown>;
  schedule?: Record<string, unknown>;
  created_at?: string;
  last_run_at?: string | null;
};

export type AgentThought = Record<string, unknown>;

export type WatchRun = {
  id: string;
  watch_id: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  tasks_executed: number;
  tasks_failed: number;
  changes_detected: number;
  error_message: string | null;
  /** Short summary of agent reasoning (from browser-use model_thoughts) */
  agent_summary?: string | null;
  /** Full agent reasoning per target */
  agent_thoughts?: Array<{ target_name: string; thoughts: AgentThought[] }> | null;
};

export type EvidenceBundle = {
  id: string;
  run_id?: string;
  change_id?: string;
  impact_memo?: string;
  diff_summary?: string;
  screenshots?: Array<{ type: string; url: string }>;
  content_hash?: string;
  audit_metadata?: Record<string, unknown>;
  s3_urls?: Record<string, string>;
};

export async function listWatches(): Promise<Watch[]> {
  const r = await fetch(`${API_URL}/api/watches`);
  if (!r.ok) throw new Error("Failed to fetch watches");
  return r.json();
}

export async function getWatch(id: string): Promise<Watch> {
  const r = await fetch(`${API_URL}/api/watches/${id}`);
  if (!r.ok) throw new Error("Failed to fetch watch");
  return r.json();
}

export async function createWatch(body: {
  name: string;
  description?: string;
  type?: string;
  config?: Record<string, unknown>;
  integrations?: Record<string, unknown>;
}): Promise<Watch> {
  const r = await fetch(`${API_URL}/api/watches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("Failed to create watch");
  return r.json();
}

export async function runWatch(watchId: string): Promise<{ status: string; watch_id: string; message: string }> {
  const r = await fetch(`${API_URL}/api/watches/${watchId}/run`, { method: "POST" });
  if (!r.ok) throw new Error("Failed to run watch");
  return r.json();
}

export async function getWatchHistory(
  watchId: string,
  limit?: number,
  offset?: number
): Promise<{ watch_id: string; runs: WatchRun[]; total: number }> {
  const params = new URLSearchParams();
  if (limit != null) params.set("limit", String(limit));
  if (offset != null) params.set("offset", String(offset));
  const q = params.toString();
  const url = `${API_URL}/api/watches/${watchId}/history${q ? `?${q}` : ""}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error("Failed to fetch history");
  return r.json();
}

export async function getEvidenceBundle(bundleId: string): Promise<EvidenceBundle> {
  const r = await fetch(`${API_URL}/api/evidence/${bundleId}`);
  if (!r.ok) throw new Error("Evidence bundle not found");
  return r.json();
}

export type RecentRun = WatchRun & { watch_name?: string };

export async function getRun(runId: string): Promise<WatchRun & { watch_name?: string }> {
  const r = await fetch(`${API_URL}/api/runs/${runId}`);
  if (!r.ok) throw new Error("Run not found");
  return r.json();
}

export async function getRecentRuns(limit?: number): Promise<RecentRun[]> {
  const params = limit != null ? `?limit=${limit}` : "";
  const r = await fetch(`${API_URL}/api/runs/recent${params}`);
  if (!r.ok) throw new Error("Failed to fetch runs");
  const data = await r.json();
  return data.runs ?? [];
}
