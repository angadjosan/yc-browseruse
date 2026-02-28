**One-liner:** We're a compliance radar — describe your product, and we automatically watch every regulation and vendor policy that affects you, and ticket your team the second something changes.

We search for specific regulations and vendor policies (across multi-step flows and multiple URLs), detect changes, diff and summarize impact, then auto-create a Jira/Linear ticket with an evidence bundle — so compliance teams see what changed and why it matters, without manual page checks.

**Context / problem scale:**
- [Risk & Compliance Magazine](https://riskandcompliancemagazine.com/the-power-of-regtech-navigating-the-regulatory-burden): 64,152 alerts annually.
- [Thomson Reuters](https://legal.thomsonreuters.com/en/insights/articles/cost-compliance-changing-world-regulation): ~200 regulatory updates per day.

---

# Compliance Change Radar — Product Requirements Document (PRD)

## 1. Overview

**In short:** You give us a description of your product. We identify key compliance-related issues and build a **watch** for each. You can add specific regulation types and create custom watches. Each watch is an **orchestrator (Claude) agent** that **assigns tasks** to **browser-use subagents**: they **search for specific regulations** (and vendor policies), not just visit fixed URLs — navigating **multi-step forms across multiple URLs** as the orchestrator directs. Runs happen on a schedule. The system does **retries and self-healing** at the orchestrator level. When a watch detects a change, it produces an issue summary, creates a **Linear** ticket, pings **Slack**, and attaches a **diff, memo, and evidence bundle** that is judge-friendly and audit-ready.

**What it is:** An agent that **searches for** specific regulations and vendor policies, with the orchestrator assigning which regulations to find and which flows to follow. Subagents use a real browser to **navigate multi-step forms across multiple URLs** (login, search, filters, detail pages), capture full page state (text + screenshot), and compare to the previous run. On change: structured diff, impact summary, evidence bundle, auto-ticket (Jira/Linear), and optional Slack alert. Compliance and legal get “what changed and why it matters” without manually re-checking or re-searching.

---

## 2. Goals & Success Metrics

| Goal | Success metric |
|------|----------------|
| Reduce manual re-checking of policy/regulator sources | Number of regulations/sources monitored per customer; time-to-notification on change |
| Reliable change detection | % of runs that correctly detect change vs. no-change; false positive rate |
| Audit-ready evidence | Every change has: diff, memo, screenshot(s), content hash; ticket created and evidence attached |
| Resilient operation | Retries and self-healing so transient failures don’t require manual intervention |

---

## 3. User Personas

- **Compliance / Legal lead:** Wants to know when anything relevant to the product changes (regulations, vendor ToS, SLAs). Needs a ticket + evidence, not a raw list of URLs.
- **Compliance analyst:** Needs to triage “what changed and why it matters” quickly; evidence must be trustworthy (hashes, timestamps, screenshots).
- **Ops / Eng:** May configure watches, schedules, and integrations (Linear, Slack); cares that runs are reliable and recover from failures.

---

## 4. Product Description (Fleshed Out)

### 4.1 Inputs

- **Product description:** Free-text description of the customer’s product (or company). Used to **identify key compliance-related issues** and suggest which regulations/vendor policies to watch.
- **Explicit watch config (optional):** User can add specific regulation types (e.g. GDPR, CCPA, sector rules), vendor ToS/SLAs, or internal policy topics, and create **custom watches** — the system will search for and monitor those (not just hit fixed URLs).

### 4.2 Watches

- A **watch** = one monitored “area” (e.g. “GDPR guidance for EU”, “Vendor X ToS”, “Internal data retention policy”).
- Each watch has:
  - **Target(s):** Regulation/policy identifiers or topics to search for (not just fixed URLs).
  - **Schedule:** e.g. daily (or configurable) runs.
  - **Orchestrator:** A Claude agent that **assigns tasks** to **browser-use subagents** — e.g. "search for [regulation X]", "follow this multi-step form across these URLs", "capture the current guidance page".
  - **Subagents:** Do **not** just visit URLs. They **search for specific regulations** (and vendor policies), navigate **multi-step forms across multiple URLs** as assigned, handle login and JS-heavy pages, capture **text + screenshot + hash** for each found target, and return results to the orchestrator.
- **Retries + self-healing:** The orchestrator can retry failed subagent runs, assign alternative search paths or URL sequences, or skip and report partial results so one failed step doesn’t kill the whole watch.

### 4.3 What we search for and traverse

- **Regulations** (e.g. GDPR, CCPA, sector-specific rules) — subagents search for them and follow regulator sites’ multi-step forms across multiple URLs.
- **Vendor terms of service, SLAs, and policy pages** — found via search and navigation as the orchestrator assigns.
- **Internal policy or compliance docs** — when topics or entry points are provided; subagents search and navigate to the relevant content.
- Flows can span **multiple URLs**, login, multi-step forms, and heavy JS — subagents use a real browser to search, navigate, and capture what a human would see.
- **Output per run:** Snapshot (text + screenshot + hash) per found target, stored so the next run can **diff** and flag deltas.

### 4.4 Detection and output (per watch run)

- **Each scheduled run:** Orchestrator **assigns** each subagent tasks to **search for** the relevant regulations/policies and **traverse multi-step flows across multiple URLs**; subagents execute, land on the relevant pages, extract text, take screenshots, compute hash.
- **Diff:** Compare current snapshot to last stored snapshot (by target).
- **When a change is detected:**
  - Structured **diff** (what text/content changed).
  - Short **impact summary / memo** (“what changed and why it matters”).
  - **Evidence bundle:** Screenshots (before/after if available), content hash, timestamp.
- **Auto-actions:**
  - Create **Linear** (or Jira) ticket: title, description, impact memo, link to evidence.
  - Attach evidence (diff, memo, screenshots) to the ticket so it’s **judge-friendly and audit-ready**.
  - **Slack** notification: link to ticket + one-line summary (optional per watch).

### 4.5 Why an agent

Regulations and vendor policies live on sites that are often non-API, anti-scrape, and require **search + multi-step navigation across many URLs**. A browser agent can search for specific regulations, log in, fill forms, follow multi-step flows across multiple pages, and capture exactly what a compliance officer would see — then automate diffing, summarizing, and creating tickets and evidence bundles so the team focuses on interpreting impact.

---

## 5. Watch Lifecycle (Flow)

1. **Setup:** User provides product description and/or explicit watch list → system creates watches (orchestrator + regulation/topic targets per watch).
2. **Schedule:** Each watch runs on its schedule (e.g. daily); orchestrator starts run.
3. **Assign & capture:** Orchestrator **assigns** each browser-use subagent tasks (e.g. search for regulation X, follow multi-step form across URLs A→B→C). Subagents **search for** the assigned regulations, navigate **multi-step forms across multiple URLs**, extract text, take screenshots, compute hash → return snapshot(s).
4. **Persist:** Store snapshot (keyed by watch + target + run timestamp).
5. **Diff:** Compare current snapshot to previous snapshot for that watch+target.
6. **Trigger:** If change detected → generate diff, impact memo, evidence bundle.
7. **Notify:** Create Linear ticket with evidence attached; send Slack ping (if enabled).
8. **Retries / self-healing:** On subagent failure, orchestrator retries or adapts (e.g. assign different search path or URL sequence, skip and report) so the watch completes or fails with a clear status.

---

## 6. Integrations

- **Linear (primary):** Create issue on trigger; attach diff, memo, screenshots; optional custom fields (e.g. “Compliance Watch”, “Evidence hash”).
- **Jira:** Same as above where Jira is chosen instead of Linear.
- **Slack:** Optional notification per watch with link to ticket and one-line summary.

---

## 7. Evidence Bundle & Auditability

Every triggered watch must produce:

- **Diff:** Machine- and human-readable (e.g. text diff or structured delta).
- **Memo:** Short impact summary (“what changed and why it matters”).
- **Screenshots:** Current (and when possible previous) state of the page(s) reached across the multi-step flow.
- **Content hash:** So integrity of captured content can be verified.
- **Timestamp / run id:** So the run is traceable.

All of the above are attached to the Linear (or Jira) ticket so the output is **judge-friendly and audit-ready**.

---

## 8. Schedule, Retries, and Self-Healing

- **Schedule:** Watches run on a defined cadence (e.g. daily); configurable per watch.
- **Retries:** Orchestrator retries failed subagent tasks (e.g. navigation timeout, element not found) with backoff or alternative strategies.
- **Self-healing:** Orchestrator can adjust assigned tasks (e.g. “try different search query”, “accept cookie banner first", "use alternative URL sequence") so that transient UI or network issues don’t require manual intervention. If a regulation/search path is unreachable after retries, the watch still completes and reports partial results + failure reason.

---

## 9. Success Criteria (Recap)

- **Detected change correctly:** Diff and trigger only when content actually changed (minimize false positives/negatives).
- **Ticket created:** Linear (or Jira) issue created with title, description, impact memo.
- **Evidence attached:** Diff, memo, screenshots, hash attached to ticket.
- **Reliability:** Watches complete or fail with clear status; retries and self-healing reduce manual reruns.

---

## 10. Demo Moment


Section 10 is your demo moment: *"We search for the regulation, traverse the multi-step flow across several URLs; within ~20 seconds we have diff + memo + ticket + evidence screenshots + hash."*

That's a **backend plumbing demo.** I'm watching a spinner for 20 seconds and then seeing a Jira ticket. Where's the wow? Where's the moment where I feel the pain before you solve it?

Here's what a strong demo looks like for this product:
1. Open with a real scenario — "Last week, the CFPB updated their guidance on buy-now-pay-later. A compliance analyst at a fintech found out two weeks later from a lawyer. That cost them $40k in legal fees."
2. Show me your product catching that change automatically, the moment it happened.
3. Show me the ticket it created, with the diff and the impact memo already written.
4. Ask me: "Would you rather find out from a lawyer, or from this?"

That's the demo. Right now you have the plumbing described but not the story.
---

## 11. Non-Goals / Out of Scope (for this PRD)

- Legal advice or interpretation of whether a change *requires* action.
- Automated remediation (e.g. changing internal policies); we only **detect, summarize, and ticket**.
- Full compliance workflow (approvals, attestations); we focus on **change detection and evidence bundle**.

---

## 12. Open Questions / Future Work

- Exact schema for “product description → suggested watches” (e.g. taxonomy of regulations per industry).
- How the orchestrator assigns search tasks and URL sequences to subagents (templates, learned paths, user hints).
- Retention of snapshots and evidence (how long to keep, where to store).
- Rate limits and politeness (crawl delay, concurrency per domain).
- Support for more issue trackers or notification channels.
