import type { Watch, ChangeEvent, Run, GlobePoint } from "./types";
import { getAccessToken } from "./supabase";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  const token = await getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function get<T>(path: string): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, { headers });
  if (res.status === 401) throw new AuthError("Unauthorized");
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) throw new AuthError("Unauthorized");
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers,
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new AuthError("Unauthorized");
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const headers = await authHeaders();
  const res = await fetch(`${BASE}${path}`, { method: "DELETE", headers });
  if (res.status === 401) throw new AuthError("Unauthorized");
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthError";
  }
}

export type UserProfile = {
  user: {
    id: string;
    email: string;
    role: string;
    organizationId: string;
  };
  organization: {
    id: string;
    name: string;
    slug: string;
    plan: string;
  };
};

export const api = {
  auth: {
    me: (): Promise<UserProfile> => get<UserProfile>("/api/me"),
  },
  watches: {
    list: (): Promise<Watch[]> =>
      get<Watch[]>("/api/watches"),
    get: (id: string): Promise<Watch> =>
      get<Watch>(`/api/watches/${id}`),
    create: (body: CreateWatchBody): Promise<Watch> =>
      post<Watch>("/api/watches", body),
    update: (id: string, body: Partial<Pick<Watch, "name" | "description"> & { schedule?: { cron: string }; integrations?: Record<string, string> }>): Promise<Watch> =>
      patch<Watch>(`/api/watches/${id}`, body),
    delete: (id: string): Promise<{ status: string }> =>
      del<{ status: string }>(`/api/watches/${id}`),
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
  type?: string;
  config: {
    targets: Array<{
      name: string;
      starting_url?: string;
      search_query?: string;
      extraction_instructions: string;
    }>;
  };
  integrations?: {
    linear_team_id?: string;
  };
  schedule?: {
    cron: string;
  };
};

export type OnboardRiskRaw = {
  regulation_title: string;
  risk_rationale: string;
  jurisdiction: string;
  scope: string;
  source_url: string;
  check_interval_seconds: number;
};

export type OnboardLog = {
  t: number;
  msg: string;
};

export type OnboardStatus = {
  job_id?: string;
  status: "pending" | "running" | "completed" | "completed_with_errors" | "failed";
  product_url?: string;
  risks_identified?: number;
  watches_created?: number;
  watches_failed?: number;
  watches?: Watch[];
  risks?: OnboardRiskRaw[];
  logs?: OnboardLog[];
  product_info?: {
    content_preview: string;
    url: string;
  };
  error?: string;
};
