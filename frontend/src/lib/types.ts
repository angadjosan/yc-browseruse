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
  riskRationale?: string;
  jurisdiction?: string;
  scope?: string;
  sourceUrl?: string;
  checkIntervalSeconds?: number;
  currentRegulationState?: string;
  type?: string;
  totalRuns?: number;
  totalChanges?: number;
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
  complianceSummary?: string;
  changeSummary?: string;
};

export type TicketData = {
  provider: "linear" | "jira";
  url: string;
  title: string;
};

export type AgentThought = {
  target_name: string;
  thoughts: Record<string, unknown>[];
};

export type Run = {
  id: string;
  watchId: string;
  watchName?: string;
  status: "running" | "completed" | "failed";
  startedAt: string;
  endedAt: string;
  steps: RunStep[];
  selfHealed: boolean;
  retries: number;
  artifacts: EvidenceArtifact[];
  diff: DiffData;
  ticket: TicketData;
  impactMemo?: string[];
  agentThoughts?: AgentThought[];
  agentSummary?: string;
};

export type GlobePoint = {
  lat: number;
  lng: number;
  label: string;
  type: "regulator" | "vendor";
  jurisdiction: string;
};

export type OnboardRisk = {
  regulation_title: string;
  risk_rationale: string;
  jurisdiction: string;
  scope: string;
  source_url: string;
  check_interval_seconds: number;
};
