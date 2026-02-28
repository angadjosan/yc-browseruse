**One-liner:** We watch regulator and vendor-policy pages, detect changes, diff and summarize impact, then auto-create a Jira/Linear ticket with an evidence bundle — so compliance teams see what changed and why it matters, without manual page checks.

**In short:** You add URLs to watch (regulator sites, vendor terms, internal policy pages). An agent navigates them on a schedule, captures text and screenshots, diffs against the last run, and when something changes it creates a ticket (Jira/Linear), pings Slack, and attaches the diff, memo, and evidence — judge-friendly and audit-ready.

---

**Compliance Change Radar — auto-ticket + evidence bundle**

**What it is**  
An agent that visits **live** regulator and vendor-policy pages (often awkward to navigate — multi-step, auth, or dynamic content), captures full page state (text + screenshot), and compares it to the previous run. When a change is detected, it diffs the content, summarizes impact, creates a Jira or Linear ticket, pings Slack, and bundles evidence (screenshots, hashes, memo). Compliance and legal teams get “what changed and why it matters” without manually re-checking dozens of URLs.

**What we watch**  
- Regulator pages (e.g. GDPR, CCPA, sector-specific rules), vendor terms of service, SLAs, and internal policy or compliance docs.  
- Pages can be behind login, multi-step flows, or heavy JS — the agent uses a real browser to navigate and capture what a human would see.  
- Output per run: snapshot (text + screenshot + hash), stored so the next run can diff and flag deltas.

**Detection and output**  
- On each scheduled run, the agent loads each watched URL, extracts text and takes screenshots, then diffs against the last stored snapshot.  
- When a change is detected: structured diff, short impact summary, and evidence bundle (screenshots, content hash).  
- Auto-actions: create Jira/Linear ticket with title, description, impact memo, and attach evidence; optional Slack notification with link to ticket and one-line summary.  
- Success metrics: “detected change correctly”, “ticket created”, “evidence attached” — so you can measure reliability and audit trail.

**Sponsor usage**  
- **Browser Use:** Navigate and capture text/screenshot behind weird flows (auth, multi-step, dynamic).  
- **Convex:** Scheduled runs, store page snapshots, diff pipeline.  
- **Laminar:** Trace each run, show replay when something breaks.  
- **HUD:** Success metric (“detected change correctly”, “ticket created”).  
- **Vercel:** Dashboard (“Watched pages”, “Diffs”, “Runs”).

**Output**  
Per watched page: current snapshot (text, screenshot, hash). On change: diff, impact memo, ticket (Jira/Linear) with evidence attached, and optional Slack alert. Demo moment: *“Page changed → within 20 seconds we have diff + memo + ticket + evidence screenshots + hash.”*

**Why an agent**  
Regulator and vendor pages are often non-API, anti-scrape, or require clicks and navigation. A browser agent can log in, follow multi-step flows, and capture exactly what a compliance officer would see — then automate the tedious bits (diffing, summarizing, creating tickets and evidence bundles) so the team focuses on interpreting impact, not re-reading unchanged pages.

---
