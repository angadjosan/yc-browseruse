import type { Watch, ChangeEvent, Run, GlobePoint } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export const api = {
  watches: {
    list: (): Promise<Watch[]> =>
      get<Watch[]>("/api/watches"),
    get: (id: string): Promise<Watch> =>
      get<Watch>(`/api/watches/${id}`),
    create: (body: CreateWatchBody): Promise<Watch> =>
      post<Watch>("/api/watches", body),
    run: (id: string): Promise<{ run_id: string; watch_id: string; status: string }> =>
      post(`/api/watches/${id}/run`),
    runs: (id: string): Promise<Run[]> =>
      get<{ runs: Run[] }>(`/api/watches/${id}/runs`).then((r) => r.runs),
    changes: (id: string): Promise<ChangeEvent[]> =>
      get<{ changes: ChangeEvent[] }>(`/api/watches/${id}/changes`).then((r) => r.changes),
  },
  runs: {
    recent: (): Promise<Run[]> =>
      get<{ runs: Run[] }>("/api/runs/recent").then((r) => r.runs),
    get: (id: string): Promise<Run> =>
      get<Run>(`/api/runs/${id}`),
  },
  changes: {
    list: (limit = 50): Promise<ChangeEvent[]> =>
      get<{ changes: ChangeEvent[] }>(`/api/changes?limit=${limit}`).then((r) => r.changes),
  },
  globe: {
    points: (): Promise<GlobePoint[]> =>
      get<{ points: GlobePoint[] }>("/api/globe-points").then((r) => r.points),
  },
  onboard: {
    start: (productUrl: string): Promise<{ job_id: string }> =>
      post("/api/analyze-product", { product_url: productUrl }),
    status: (jobId: string): Promise<OnboardStatus> =>
      get<OnboardStatus>(`/api/analyze-product/${jobId}`),
  },
};

export type CreateWatchBody = {
  name: string;
  description?: string;
  config: {
    targets: Array<{
      name: string;
      starting_url?: string;
      search_query?: string;
      extraction_instructions: string;
    }>;
  };
};

// Raw evidence bundle shape (as returned by backend evidence_service)
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

export async function listEvidenceBundles(limit?: number): Promise<EvidenceBundle[]> {
  const q = limit != null ? `?limit=${limit}` : "";
  const res = await fetch(`${BASE}/api/evidence${q}`);
  if (!res.ok) throw new Error(`/api/evidence → ${res.status}`);
  const data = await res.json();
  return data.bundles ?? [];
}

export async function getEvidenceBundle(bundleId: string): Promise<EvidenceBundle> {
  const res = await fetch(`${BASE}/api/evidence/${bundleId}`);
  if (!res.ok) throw new Error("Evidence bundle not found");
  return res.json();
}

export type OnboardStatus = {
  job_id?: string;
  status: "pending" | "running" | "completed" | "failed";
  product_url?: string;
  risks_identified?: number;
  watches_created?: number;
  watches?: Watch[];
  product_info?: {
    content_preview: string;
    url: string;
  };
  error?: string;
};
