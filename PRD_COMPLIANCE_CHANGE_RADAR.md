# Hackathon PRD: Compliance Change Radar

**Version:** 1.0 (Hackathon)  
**Last Updated:** February 28, 2025  
**Scope:** 24–48 hour build  
**Demo target:** Single flow, working end-to-end

---

## One-Liner

We watch regulator and vendor-policy pages, detect changes, diff and summarize impact, then auto-create a Linear ticket with an evidence bundle — so compliance teams see *what changed and why it matters* without manual page checks.

**Demo moment:** *"Page changed → within 20 seconds we have diff + memo + ticket + evidence screenshots + hash."*

---

## Table of Contents

1. [Problem](#1-problem)
2. [Hackathon Scope — Ship This](#2-hackathon-scope--ship-this)
3. [Out of Scope (Post-Hackathon)](#3-out-of-scope-post-hackathon)
4. [User Flow (Demo Script)](#4-user-flow-demo-script)
5. [UI — Minimal & Polished](#5-ui--minimal--polished)
6. [Tech Stack](#6-tech-stack)
7. [Known Limitations](#7-known-limitations)
8. [Team Division / Roles](#8-team-division--roles)

---

## 1. Problem

- **64,152** regulatory alerts annually; **200+** updates per day
- Regulator/vendor pages: non-API, anti-scrape, auth-gated, heavy JS
- Compliance teams manually re-check dozens of URLs — no audit trail
- No single source for *what changed* and *why it matters*

---

## 2. Hackathon Scope — Ship This

### Must Have (Demo-Blocking)

| Feature | Description | Effort |
|---------|-------------|--------|
| **Add 1 Watch** | User enters URL + name. No auth, no schedule — manual "Run" button only. | 1–2h |
| **Agent Run** | Browser Use agent navigates to URL, extracts text + screenshot, stores snapshot (Convex). | 2–4h |
| **Second Run → Diff** | Run again; diff text vs. last snapshot; detect change. | 2–3h |
| **Change → Linear Ticket** | On change: create Linear issue with title, impact memo, screenshot. (Linear API key in env.) | 2–3h |
| **Dashboard** | Single page: list of watches, last run status, "Run" button, list of changes with link to ticket. | 2–3h |

### Nice to Have (If Time)

- Slack notification on change
- Side-by-side diff view in UI
- AI-generated impact summary (1–2 sentences) via LLM
- Content hash (SHA-256) on snapshot for audit

### Skip for Hackathon

- Auth (or use Clerk quickstart if sponsor)
- Scheduling (cron) — manual run only
- Jira, webhooks, multiple integrations
- Product description → AI-suggested watches
- Retries / self-healing (accept failures)
- Evidence PDF, audit log, team, billing

---

## 3. Out of Scope (Post-Hackathon)

- OAuth for Linear (use API key for hackathon)
- Scheduled runs
- Multiple integrations (Jira, Slack as first-class)
- AI-suggested watches from product description
- Full edge-case handling (CAPTCHA, auth, 404, etc.)
- Multi-org, team management, audit log

---

## 4. User Flow (Demo Script)

**2-minute demo:**

1. **"Here are our watched pages"** — Show 2–3 watches (e.g. GDPR FAQ, vendor ToS).
2. **"We run the agent"** — Click "Run" on one watch. Show agent navigating (or loading state).
3. **"It captures the page"** — Show stored screenshot + text in dashboard.
4. **"We change the page"** — Manually edit a public test page, or use a page you control.
5. **"Run again"** — Click "Run". Agent captures new state.
6. **"Change detected"** — Dashboard shows new change; diff + impact memo.
7. **"Ticket in Linear"** — Open Linear; show ticket with screenshot, memo, link to evidence.
8. **"Done — under 30 seconds from change to ticket."**

---

## 5. UI — Minimal & Polished

### Design Principles

- **Professional, trustworthy** — legal/finance feel, not playful
- **One page** — avoid deep navigation
- **Clear status** — running / success / failed / change detected

### Layout

- **Single dashboard:** Watches (table or cards) + Changes (list)
- **Watches:** Name, URL (truncated), Last run, Status, "Run" button
- **Changes:** Date, watch name, impact summary, "View in Linear" link
- **Add Watch:** Simple modal or inline form — URL + name only

### Design Tokens (Quick Reference)

| Token | Value |
|-------|-------|
| Primary | `#0F172A` |
| Accent | `#3B82F6` |
| Success | `#10B981` |
| Error | `#EF4444` |
| Bg | `#F8FAFC` |
| Font | Inter or system-ui |
| Radius | 6–8px |
| Shadow | `0 1px 3px rgba(0,0,0,.08)` |

### Screens to Build

1. **Dashboard** — Watches list, Changes list, Add Watch CTA
2. **Add Watch modal** — URL, name, Save
3. **Change detail (optional)** — Diff preview, screenshot, memo, Linear link

---

## 6. Tech Stack

| Layer | Pick |
|-------|------|
| **Frontend** | Next.js + Tailwind + shadcn/ui (or Vercel template) |
| **Backend / DB** | Convex |
| **Agent** | Browser Use + ChatBrowserUse |
| **Integration** | Linear REST API (create issue) |
| **Hosting** | Vercel |
| **Auth** | Skip or Clerk (if sponsor) |

### Convex Schema (Minimal)

```
watch: { url, name, createdAt }
run: { watchId, status, startedAt, finishedAt?, error? }
snapshot: { runId, text, screenshotStorageId, contentHash? }
change: { watchId, prevSnapshotId, newSnapshotId, diff, impactMemo, linearTicketId?, linearTicketUrl? }
```

### Linear Integration

- Create issue: `POST https://api.linear.app/graphql` (or REST)
- Include: title, description (memo + diff excerpt), attachment (screenshot URL)
- Store `linearTicketId`, `linearTicketUrl` on change

---

## 7. Known Limitations

**Accept these for hackathon:**

- No auth — single-user / local only
- Public pages only — no login flows
- Manual run only — no scheduling
- Linear API key in env — no OAuth
- Simple text diff — no semantic/ignore patterns
- Failures possible — no retries or self-healing
- 404/redirect → show error, don't auto-recover

---

## 8. Team Division / Roles

| Role | Owner | Tasks |
|------|-------|-------|
| **Agent / Backend** | 1 dev | Browser Use agent, Convex schema, run/snapshot/change logic |
| **Frontend** | 1 dev | Dashboard, watches list, changes list, Add Watch |
| **Integration** | 1 dev | Linear API, ticket creation, evidence attachment |
| **Full-stack / Glue** | 1 dev | Wire Convex ↔ agent, diff logic, impact memo |

*Adjust for team size; 2–3 people can split above.*

---

## Appendix: Glossary

- **Watch** — A monitored URL
- **Run** — Single agent execution (navigate, capture, store)
- **Snapshot** — Stored text + screenshot from a run
- **Change** — Detected delta between two snapshots → triggers ticket

---

*Hackathon PRD — ship the demo, polish later.*
