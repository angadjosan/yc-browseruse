export type Watch = {
  id: string;
  name: string;
  description: string;
  schedule: string;
  jurisdictions: string[];
  sources: string[];
  status: "healthy" | "degraded";
  nextRunAt: string;
  lastRunAt: string | null;
};

export type ChangeEvent = {
  id: string;
  watchId: string;
  title: string;
  memo: string;
  severity: "low" | "med" | "high";
  jurisdiction: string;
  sourceType: "regulator" | "vendor";
  createdAt: string;
  runId: string;
};

export type RunStep = {
  name: string;
  status: "pending" | "running" | "done" | "retry";
  timestamp?: string;
};

export type EvidenceArtifact = {
  id: string;
  type: "screenshot" | "hash" | "snapshot";
  label: string;
  url?: string;
  hash?: string;
  timestamp: string;
};

export type DiffData = {
  before: string;
  after: string;
  highlights: { type: "add" | "remove" | "unchanged"; text: string }[];
};

export type TicketData = {
  provider: "linear" | "jira";
  url: string;
  title: string;
};

export type Run = {
  id: string;
  watchId: string;
  watchName?: string;
  startedAt: string;
  endedAt: string;
  steps: RunStep[];
  selfHealed: boolean;
  retries: number;
  artifacts: EvidenceArtifact[];
  diff: DiffData;
  ticket: TicketData;
  impactMemo?: string[];
};

export type GlobePoint = {
  lat: number;
  lng: number;
  label: string;
  type: "regulator" | "vendor";
  jurisdiction: string;
};
