import type { Watch, ChangeEvent, Run, GlobePoint } from "./types";

export const watches: Watch[] = [
  {
    id: "w1",
    name: "GDPR guidance for AI profiling",
    description: "EC guidance on AI and automated decision-making",
    schedule: "daily",
    jurisdictions: ["EU"],
    sources: ["European Commission"],
    status: "healthy",
    nextRunAt: "2025-03-01T14:00:00Z",
    lastRunAt: "2025-03-01T08:00:00Z",
  },
  {
    id: "w2",
    name: "Stripe ToS",
    description: "Stripe terms of service and acceptable use",
    schedule: "weekly",
    jurisdictions: ["US"],
    sources: ["Stripe"],
    status: "healthy",
    nextRunAt: "2025-03-03T09:00:00Z",
    lastRunAt: "2025-02-28T09:00:00Z",
  },
  {
    id: "w3",
    name: "HIPAA tracking pixels",
    description: "HHS guidance on tracking technologies and PHI",
    schedule: "daily",
    jurisdictions: ["US"],
    sources: ["HHS"],
    status: "degraded",
    nextRunAt: "2025-03-01T12:00:00Z",
    lastRunAt: "2025-02-28T12:00:00Z",
  },
  {
    id: "w4",
    name: "CCPA disclosure requirements",
    description: "California AG regulations on privacy notices",
    schedule: "weekly",
    jurisdictions: ["US-CA"],
    sources: ["California DOJ"],
    status: "healthy",
    nextRunAt: "2025-03-05T10:00:00Z",
    lastRunAt: "2025-02-27T10:00:00Z",
  },
  {
    id: "w5",
    name: "AWS Service Terms",
    description: "AWS customer agreement and policy changes",
    schedule: "weekly",
    jurisdictions: ["US"],
    sources: ["AWS"],
    status: "healthy",
    nextRunAt: "2025-03-04T00:00:00Z",
    lastRunAt: "2025-02-27T00:00:00Z",
  },
];

export const changeEvents: ChangeEvent[] = [
  {
    id: "c1",
    watchId: "w1",
    title: "GDPR guidance for AI profiling",
    memo: "New section on explainability requirements for profiling.",
    severity: "high",
    jurisdiction: "EU",
    sourceType: "regulator",
    createdAt: "2025-03-01T08:15:00Z",
    runId: "r1",
  },
  {
    id: "c2",
    watchId: "w2",
    title: "Stripe ToS",
    memo: "Acceptable use policy updated; crypto mining clarified.",
    severity: "med",
    jurisdiction: "US",
    sourceType: "vendor",
    createdAt: "2025-02-28T09:22:00Z",
    runId: "r2",
  },
  {
    id: "c3",
    watchId: "w3",
    title: "HIPAA tracking pixels",
    memo: "FAQ revised on third-party tracking on health provider sites.",
    severity: "high",
    jurisdiction: "US",
    sourceType: "regulator",
    createdAt: "2025-02-28T12:45:00Z",
    runId: "r3",
  },
  {
    id: "c4",
    watchId: "w4",
    title: "CCPA disclosure requirements",
    memo: "Minor wording change in example disclosure language.",
    severity: "low",
    jurisdiction: "US-CA",
    sourceType: "regulator",
    createdAt: "2025-02-27T10:30:00Z",
    runId: "r4",
  },
  {
    id: "c5",
    watchId: "w5",
    title: "AWS Service Terms",
    memo: "Data processing terms updated for EU DPA.",
    severity: "med",
    jurisdiction: "US",
    sourceType: "vendor",
    createdAt: "2025-02-27T00:18:00Z",
    runId: "r5",
  },
];

export const runs: Run[] = [
  {
    id: "r1",
    watchId: "w1",
    watchName: "GDPR guidance for AI profiling",
    startedAt: "2025-03-01T08:00:00Z",
    endedAt: "2025-03-01T08:02:15Z",
    steps: [
      { name: "Searching", status: "done", timestamp: "08:00:01" },
      { name: "Navigating", status: "done", timestamp: "08:00:45" },
      { name: "Capturing", status: "done", timestamp: "08:01:10" },
      { name: "Hashing", status: "done", timestamp: "08:01:35" },
      { name: "Diffing", status: "done", timestamp: "08:01:50" },
      { name: "Ticketing", status: "done", timestamp: "08:02:15" },
    ],
    selfHealed: false,
    retries: 0,
    artifacts: [
      { id: "a1", type: "screenshot", label: "Before", url: "/placeholder-before.png", timestamp: "2025-03-01T08:01:10Z" },
      { id: "a2", type: "screenshot", label: "After", url: "/placeholder-after.png", timestamp: "2025-03-01T08:01:10Z" },
      { id: "a3", type: "hash", label: "Content hash", hash: "sha256:a1b2c3d4e5f6...", timestamp: "2025-03-01T08:01:35Z" },
    ],
    diff: {
      before: "Previous version had no explainability section for profiling.",
      after: "New section 4.2: Systems used for profiling must provide meaningful explanation of the logic involved.",
      highlights: [
        { type: "remove", text: "No specific explainability requirement." },
        { type: "add", text: "Section 4.2: meaningful explanation of logic required." },
      ],
    },
    ticket: { provider: "linear", url: "https://linear.app/team/issue/CR-101", title: "GDPR AI guidance updated" },
    impactMemo: ["Review explainability implementation.", "Update consent flows if needed."],
  },
  {
    id: "r2",
    watchId: "w2",
    watchName: "Stripe ToS",
    startedAt: "2025-02-28T09:00:00Z",
    endedAt: "2025-02-28T09:01:22Z",
    steps: [
      { name: "Searching", status: "done", timestamp: "09:00:01" },
      { name: "Navigating", status: "done", timestamp: "09:00:30" },
      { name: "Capturing", status: "done", timestamp: "09:00:55" },
      { name: "Hashing", status: "done", timestamp: "09:01:05" },
      { name: "Diffing", status: "done", timestamp: "09:01:15" },
      { name: "Ticketing", status: "done", timestamp: "09:01:22" },
    ],
    selfHealed: false,
    retries: 0,
    artifacts: [
      { id: "b1", type: "screenshot", label: "ToS page", url: "/placeholder-before.png", timestamp: "2025-02-28T09:00:55Z" },
      { id: "b2", type: "hash", label: "Content hash", hash: "sha256:f6e5d4c3b2a1...", timestamp: "2025-02-28T09:01:05Z" },
    ],
    diff: {
      before: "Acceptable use: no mention of crypto mining.",
      after: "Acceptable use: crypto mining and related high-compute use cases are prohibited unless explicitly permitted.",
      highlights: [
        { type: "add", text: "Crypto mining prohibited unless permitted." },
      ],
    },
    ticket: { provider: "linear", url: "https://linear.app/team/issue/CR-102", title: "Stripe ToS – acceptable use update" },
    impactMemo: ["Confirm we do not offer mining-related services.", "No product change required."],
  },
  {
    id: "r3",
    watchId: "w3",
    watchName: "HIPAA tracking pixels",
    startedAt: "2025-02-28T12:00:00Z",
    endedAt: "2025-02-28T12:02:45Z",
    steps: [
      { name: "Searching", status: "done", timestamp: "12:00:01" },
      { name: "Navigating", status: "done", timestamp: "12:00:50" },
      { name: "Capturing", status: "done", timestamp: "12:01:20" },
      { name: "Hashing", status: "done", timestamp: "12:01:45" },
      { name: "Diffing", status: "done", timestamp: "12:02:10" },
      { name: "Ticketing", status: "done", timestamp: "12:02:45" },
    ],
    selfHealed: true,
    retries: 1,
    artifacts: [
      { id: "c1", type: "screenshot", label: "FAQ section", url: "/placeholder-after.png", timestamp: "2025-02-28T12:01:20Z" },
      { id: "c2", type: "hash", label: "Content hash", hash: "sha256:1a2b3c4d5e6f...", timestamp: "2025-02-28T12:01:45Z" },
    ],
    diff: {
      before: "FAQ stated tracking technologies may require BAA in some cases.",
      after: "FAQ revised: tracking technologies that involve PHI are subject to BAA and must be disclosed.",
      highlights: [
        { type: "remove", text: "may require BAA in some cases" },
        { type: "add", text: "subject to BAA and must be disclosed" },
      ],
    },
    ticket: { provider: "jira", url: "https://jira.company.com/browse/COMP-88", title: "HIPAA tracking FAQ update" },
    impactMemo: ["Audit tracking pixels on health pages.", "Ensure BAAs in place for vendors."],
  },
];

export const globePoints: GlobePoint[] = [
  { lat: 50.85, lng: 4.35, label: "European Commission", type: "regulator", jurisdiction: "EU" },
  { lat: 38.9, lng: -77.0, label: "HHS", type: "regulator", jurisdiction: "US" },
  { lat: 37.77, lng: -122.42, label: "Stripe", type: "vendor", jurisdiction: "US" },
  { lat: 47.61, lng: -122.33, label: "AWS", type: "vendor", jurisdiction: "US" },
  { lat: 37.77, lng: -122.42, label: "California DOJ", type: "regulator", jurisdiction: "US-CA" },
  { lat: 51.51, lng: -0.09, label: "ICO UK", type: "regulator", jurisdiction: "UK" },
  { lat: 35.68, lng: 139.69, label: "PPC Japan", type: "regulator", jurisdiction: "JP" },
];

export function getRunById(id: string): Run | undefined {
  return runs.find((r) => r.id === id);
}

export function getChangesByJurisdiction(jurisdiction: string | null): ChangeEvent[] {
  if (!jurisdiction) return changeEvents;
  return changeEvents.filter((c) => c.jurisdiction === jurisdiction);
}

export function getWatchesByJurisdiction(jurisdiction: string | null): Watch[] {
  if (!jurisdiction) return watches;
  return watches.filter((w) => w.jurisdictions.includes(jurisdiction));
}
