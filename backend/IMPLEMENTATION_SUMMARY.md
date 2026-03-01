# Implementation Summary: AI Workflow for Compliance Monitoring

This document summarizes the changes made to implement the orchestration workflow described in `markdown/ai_workflow.md`.

## Overview

The new workflow transforms the system from a generic compliance monitoring tool into an intelligent regulatory change detector that:
1. Analyzes product pages to identify compliance risks
2. Creates automated watches for each regulatory risk
3. Spawns research agents when changes are detected to gather comprehensive context
4. Generates actionable compliance guidance and change summaries

## Changes Made

### 1. New Service: ProductAnalyzer (`app/services/product_analyzer.py`)

**Purpose:** Orchestrates the initial product analysis workflow.

**Key Methods:**
- `analyze_product_url(product_url, organization_id)` - Main entry point for the workflow
- `extract_product_info(product_url)` - Uses browser-use agent (custom BU model) to extract product information from landing page
- `generate_risk_analysis(product_info, product_url)` - Uses Claude (CLAUDE_MODEL) to:
  - Understand what the product does
  - Generate comprehensive list of compliance risks (major and microscopic)
  - For each risk: regulation title, risk rationale, jurisdiction, scope, source URL, check interval
- `_fetch_initial_regulation_state(risk)` - Uses browser-use to fetch current state of each regulation
- `create_watches_from_risks(risks, organization_id, product_url)` - Creates watches for all identified risks

**Output Format:**
Each risk includes:
- `regulation_title`: Name of regulation
- `risk_rationale`: Why it applies (2-3 sentences)
- `jurisdiction`: Geographic scope
- `scope`: Affected aspects
- `source_url`: Official regulation URL
- `check_interval_seconds`: Monitoring frequency
- `current_state`: Initial regulation snapshot

### 2. Enhanced WatchService (`app/services/watch_service.py`)

**New Fields Added:**
- `regulation_title` - Title of the regulation being monitored
- `risk_rationale` - Why this regulation applies to the product
- `jurisdiction` - Geographic scope (EU, California, etc.)
- `scope` - What aspects of product are affected
- `source_url` - Official regulation URL
- `check_interval_seconds` - How often to check (stored alongside schedule)
- `current_regulation_state` - Persisted text of regulation, updated on each run

**New Methods:**
- `update_regulation_state(watch_id, new_state)` - Updates the current regulation state after each run

### 3. Enhanced DiffEngine (`app/services/diff_engine.py`)

**New Methods:**

`generate_compliance_summary(change_details, regulation_title, research_findings)`
- Generates actionable guidance on HOW TO COMPLY with detected changes
- Considers: immediate actions, timeline, resources, risk mitigation, stakeholders
- Uses research findings from additional browser agents for context

`generate_change_summary(old_content, new_content, regulation_title, research_findings)`
- Generates detailed summary of WHAT CHANGED in the regulation
- Includes: what was added/removed/modified, why change occurred, scope, effective date
- Incorporates research context from news, guidance docs, consulting analyses

### 4. Enhanced Orchestrator (`app/services/orchestrator.py`)

**Modified Change Detection Flow:**

When a regulatory change is detected, the orchestrator now:

1. **Spawns Research Agents** (up to 15 browser-use agents)
   - Uses Claude to generate 10-15 targeted research queries
   - Queries target: news articles, official guidance, consulting analyses, press releases
   - Each agent navigates multi-step pages to extract comprehensive information
   - Returns research findings with content, URLs, and summaries

2. **Generates Enhanced Summaries**
   - Compliance summary: how to comply with the change
   - Change summary: detailed explanation of what changed
   - Both summaries incorporate research context

3. **Updates Watch State**
   - Updates `current_regulation_state` field with new regulation text
   - This becomes the baseline for the next comparison

**New Method:**
- `_research_regulatory_change(watch, change, current_snapshot, previous_snapshot)`
  - Orchestrates the research agent spawning
  - Returns list of research findings

### 5. Enhanced NotificationHub (`app/services/notification_hub.py`)

**Updated Method:**
`notify_change()` now includes:
- `compliance_summary` - How to comply (added to Linear description and Slack message)
- `change_detail_summary` - What changed (added to Linear description and Slack message)

**Linear Issue Format:**
```markdown
## Change Summary
[Semantic diff summary]

**Impact Level:** [low/medium/high/critical]

## What Changed
[Detailed change summary from research]

## How to Comply
[Actionable compliance guidance]

[View Evidence](url)
```

**Slack Message Format:**
- Includes change summary, impact level
- Truncated "what changed" summary (300 chars)
- Link to full Linear ticket

### 6. New API Endpoint (`app/api/routes.py`)

**POST /api/analyze-product**

Request:
```json
{
  "product_url": "https://example.com/product"
}
```

Response:
```json
{
  "status": "success",
  "product_url": "https://example.com/product",
  "product_info": {
    "content_preview": "...",
    "url": "..."
  },
  "risks_identified": 15,
  "watches_created": 15,
  "watches": [...]
}
```

**Workflow:**
1. Extract product information using browser-use
2. Generate compliance risk analysis using Claude
3. Create watches for each identified risk
4. Return created watches

### 7. Updated Schemas (`app/schemas/watch.py`)

**WatchResponse** now includes:
- `regulation_title`
- `risk_rationale`
- `jurisdiction`
- `scope`
- `source_url`
- `check_interval_seconds`
- `current_regulation_state`

## Complete Workflow

### Initial Setup (New Product Analysis)

1. **User inputs product URL** via POST /api/analyze-product
2. **Phase 1 - Product Extraction**
   - Browser-use agent (custom BU model) navigates product page
   - Extracts: features, use cases, data handling, integrations, regions
3. **Phase 2 - Risk Analysis**
   - Claude analyzes product information
   - Identifies 10-20+ compliance risks (major + microscopic)
   - For each risk, fetches initial regulation state via browser-use
4. **Phase 3 - Watch Creation**
   - Creates one watch per identified risk
   - Each watch stores: regulation title, rationale, jurisdiction, scope, check interval, current state

### Ongoing Monitoring (Watch Execution)

1. **Scheduled Execution**
   - Watch runs based on `check_interval_seconds` (hourly/daily/weekly)
2. **Content Extraction**
   - Claude agent spawns browser-use subagents (custom BU model)
   - Extracts current regulation text
3. **Change Detection**
   - Compares current content vs. `current_regulation_state`
   - If hash differs, runs text diff + semantic diff
4. **Research Phase** (if change detected)
   - Claude generates 10-15 targeted research queries
   - Spawns up to 15 browser-use agents in parallel
   - Agents search: news, guidance docs, consulting analyses, Reuters, etc.
   - Agents navigate multi-step pages for comprehensive info
5. **Analysis Phase**
   - Generates "language diff" (exact text changes)
   - Generates "compliance summary" (how to comply)
   - Generates "change summary" (what changed and why)
   - Updates watch's `current_regulation_state`
6. **Notification Phase**
   - Creates Linear ticket with all summaries
   - Sends Slack message with key details
   - Stores change record with research findings

## Key Design Decisions

1. **Browser-Use Model:** All browser-use agents use `ChatBrowserUse()` (custom BU model) as specified
2. **Claude Model:** Main Claude calls use `CLAUDE_MODEL` from config (default: claude-sonnet-4-20250514)
3. **Research Agent Limit:** Maximum 15 agents to balance thoroughness with cost/performance
4. **State Persistence:** `current_regulation_state` stored on watch, not just in snapshots
5. **Parallel Execution:** Research agents run concurrently via `asyncio.gather()`
6. **Fallback Handling:** System gracefully degrades if browser-use or Claude unavailable

## Database Schema Requirements

The implementation assumes the `watches` table includes these columns:
- `regulation_title` (text, nullable)
- `risk_rationale` (text, nullable)
- `jurisdiction` (text, nullable)
- `scope` (text, nullable)
- `source_url` (text, nullable)
- `check_interval_seconds` (integer, nullable)
- `current_regulation_state` (text, nullable)

The `changes` table should support JSONB `diff_details` that includes:
- `text_diff`
- `semantic_diff`
- `compliance_summary`
- `change_summary`
- `research_findings`

## Files Modified

1. ✅ `app/services/product_analyzer.py` (NEW)
2. ✅ `app/services/watch_service.py`
3. ✅ `app/services/diff_engine.py`
4. ✅ `app/services/orchestrator.py`
5. ✅ `app/services/notification_hub.py`
6. ✅ `app/services/__init__.py`
7. ✅ `app/api/routes.py`
8. ✅ `app/schemas/watch.py`

## Testing Recommendations

1. **Product Analysis Flow:**
   - Test POST /api/analyze-product with various product URLs
   - Verify browser-use extraction works correctly
   - Verify Claude generates comprehensive risk list (10-20+ risks)
   - Verify watches are created with all fields populated

2. **Watch Execution with Changes:**
   - Manually trigger a watch run
   - Verify research agents spawn when change detected
   - Verify compliance and change summaries are generated
   - Verify Linear ticket and Slack message include all summaries

3. **Database Persistence:**
   - Verify `current_regulation_state` updates after each run
   - Verify research findings stored in `changes.diff_details`
   - Verify watch metadata (regulation_title, jurisdiction, etc.) persists

4. **Error Handling:**
   - Test with missing API keys (graceful degradation)
   - Test with browser-use failures (retries + fallbacks)
   - Test with invalid product URLs (error handling)

## Environment Variables Required

- `ANTHROPIC_API_KEY` - For Claude API calls
- `CLAUDE_MODEL` - Model to use (default: claude-sonnet-4-20250514)
- `BROWSER_USE_API_KEY` - For browser-use cloud agents
- `LINEAR_API_KEY` - For Linear integration
- `SLACK_BOT_TOKEN` - For Slack notifications
- `SUPABASE_URL` - Database connection
- `SUPABASE_SERVICE_ROLE_KEY` - Database authentication

## Next Steps

1. **Database Migration:** Add new columns to `watches` table
2. **Testing:** Run end-to-end tests with real product URLs
3. **UI Updates:** Update frontend to display new regulation fields
4. **Monitoring:** Add logging/metrics for research agent success rates
5. **Cost Optimization:** Monitor token usage for research agents, adjust limits if needed
