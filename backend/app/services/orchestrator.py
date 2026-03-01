"""Claude-powered orchestrator: main agent spawns browser-use subagents via tools.

When ANTHROPIC_API_KEY and BROWSER_USE_API_KEY are set, the main Claude agent runs
in an agentic loop with a spawn_browser_agent tool. The main agent decides when
and how many subagents to spawn — no hardcoded Python loops. Fallback: non-agentic
plan + execute when only browser-use is available.
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.config import get_config
from app.db import get_supabase
from app.services.agent_harness import run_main_agent_loop
from app.services.diff_engine import DiffEngine
from app.services.evidence_service import EvidenceService
from app.services.notification_hub import NotificationHub
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


class BrowserTask(BaseModel):
    """Per-target browser task from orchestrator plan."""
    id: str
    target_name: str
    task_description: str
    starting_url: Optional[str] = None
    search_query: Optional[str] = None
    extraction_instructions: str
    fallback_strategy: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Claude-generated execution plan for a watch run."""
    watch_id: str
    run_id: str
    tasks: List[BrowserTask]
    estimated_duration: int = 0


def _task_result(
    task_id: str,
    target_name: str,
    status: str,
    content: str = "",
    content_hash: str = "",
    url: str = "",
    screenshot_url: Optional[str] = None,
    error: Optional[str] = None,
    agent_thoughts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "task_id": task_id,
        "target_name": target_name,
        "status": status,
        "content": content,
        "content_hash": content_hash,
        "url": url,
        "screenshot_url": screenshot_url,
        "timestamp": int(time.time()),
        "captured_at": datetime.utcnow().isoformat(),
        "error": error,
    }
    if agent_thoughts is not None:
        out["agent_thoughts"] = agent_thoughts
    return out


class OrchestratorEngine:
    """Claude-powered orchestrator: plan via Claude, execute via browser-use agents, retries and self-healing."""

    def __init__(self):
        self.config = get_config()
        self.watch_service = WatchService()
        self.diff_engine = DiffEngine()
        self.evidence_service = EvidenceService()
        self.notification_hub = NotificationHub()
        self._db = None
        self._anthropic = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_supabase()
        return self._db

    def _get_anthropic(self):
        if self._anthropic is None and self.config.get("anthropic_api_key"):
            from anthropic import Anthropic
            self._anthropic = Anthropic(api_key=self.config["anthropic_api_key"])
        return self._anthropic

    def _has_browser_use(self) -> bool:
        if not self.config.get("browser_use_api_key"):
            return False
        try:
            from browser_use import Agent, Browser, ChatBrowserUse  # noqa: F401
            return True
        except ImportError:
            return False

    def _has_anthropic(self) -> bool:
        return bool(self.config.get("anthropic_api_key"))

    # ── Main entry ────────────────────────────────────────────────────

    async def execute_watch(self, watch_id: str) -> Dict[str, Any]:
        """Load watch, create run, plan (Claude), execute tasks (browser-use), diff, evidence, notify."""
        watch = await self.watch_service.get_watch(watch_id)
        if not watch:
            return {"run_id": None, "status": "error", "error": "Watch not found"}

        run = await self.watch_service.create_run(watch_id, status="running")
        run_id = str(run["id"])
        start = time.time()
        changes_count = 0
        tasks_ok = 0
        tasks_fail = 0

        try:
            config = watch.get("config") or {}
            targets = config.get("targets") or [
                {
                    "name": watch.get("name", "default"),
                    "description": watch.get("description") or watch.get("name", ""),
                    "search_query": watch.get("name", ""),
                    "extraction_instructions": "Extract the main text content of the regulation or policy.",
                }
            ]

            if self._has_browser_use() and self._has_anthropic():
                logger.info(f"[run={run_id}] Using agentic harness: main agent spawns browser-use subagents")
                task_results = await self._run_agentic_harness(watch, run_id)
            elif self._has_browser_use():
                logger.info(f"[run={run_id}] Using browser-use with fallback plan (no Claude for planning)")
                plan = self._plan_from_targets(watch["id"], run_id, targets)
                task_results = await self.execute_tasks_with_retries(plan, run_id)
            else:
                logger.warning(f"[run={run_id}] browser-use unavailable — falling back to mock tasks")
                task_results = await self._execute_mock_tasks(watch_id, run_id, targets)

            for tr in task_results:
                if tr.get("status") == "success":
                    tasks_ok += 1
                else:
                    tasks_fail += 1

            # Save snapshots, diff against previous, generate evidence
            for tr in task_results:
                if tr.get("status") != "success":
                    continue
                target_name = tr.get("target_name", "default")
                current_snapshot = {
                    "content": tr.get("content", ""),
                    "content_text": tr.get("content", ""),
                    "content_hash": tr.get("content_hash"),
                    "url": tr.get("url", ""),
                    "target_name": target_name,
                    "screenshot_url": tr.get("screenshot_url"),
                    "timestamp": tr.get("timestamp"),
                    "captured_at": tr.get("captured_at"),
                }
                await self.watch_service.save_snapshot(
                    watch_id=watch_id,
                    run_id=run_id,
                    target_name=target_name,
                    url=current_snapshot["url"],
                    content_text=current_snapshot["content_text"],
                    content_hash=current_snapshot["content_hash"],
                    screenshot_url=current_snapshot.get("screenshot_url"),
                )

                # Get the previous snapshot (not from this run)
                previous = await self._get_previous_snapshot(watch_id, run_id, target_name)

                if previous:
                    change = await self.diff_engine.detect_changes(current_snapshot, previous)
                    if change.get("has_changes"):
                        changes_count += 1

                        # Enhanced workflow: spawn research agents to investigate the change
                        research_findings = []
                        if self._has_browser_use() and self._has_anthropic():
                            logger.info(f"[run={run_id}] Change detected, spawning research agents")
                            research_findings = await self._research_regulatory_change(
                                watch=watch,
                                change=change,
                                current_snapshot=current_snapshot,
                                previous_snapshot=previous,
                            )

                        # Generate enhanced summaries with research context
                        regulation_title = watch.get("regulation_title") or watch.get("name", "Unknown")
                        compliance_summary = await self.diff_engine.generate_compliance_summary(
                            change_details=change,
                            regulation_title=regulation_title,
                            research_findings=research_findings,
                        )
                        change_summary = await self.diff_engine.generate_change_summary(
                            old_content=previous.get("content_text", ""),
                            new_content=current_snapshot.get("content_text", ""),
                            regulation_title=regulation_title,
                            research_findings=research_findings,
                        )

                        # Update watch's current regulation state
                        new_state = current_snapshot.get("content_text", "")
                        await self.watch_service.update_regulation_state(watch_id, new_state)

                        change_row = {
                            "watch_id": watch_id,
                            "run_id": run_id,
                            "target_name": target_name,
                            "diff_summary": (change.get("semantic_diff") or {}).get("summary"),
                            "diff_details": {
                                "text_diff": change.get("text_diff"),
                                "semantic_diff": change.get("semantic_diff"),
                                "compliance_summary": compliance_summary,
                                "change_summary": change_summary,
                                "research_findings": research_findings[:5] if research_findings else [],
                            },
                            "impact_level": (change.get("semantic_diff") or {}).get("impact_level", "medium"),
                        }
                        cr = self.db.table("changes").insert(change_row).execute()
                        change_id = cr.data[0]["id"] if cr.data else None
                        if change_id:
                            evidence = await self.evidence_service.generate_evidence_bundle(
                                change, current_snapshot, previous, run_id, change_id
                            )
                            integrations = watch.get("integrations") or {}
                            await self.notification_hub.notify_change(
                                watch_name=watch.get("name", ""),
                                change_summary=change.get("semantic_diff", {}).get("summary", "Content changed."),
                                impact_level=change.get("semantic_diff", {}).get("impact_level", "medium"),
                                linear_team_id=integrations.get("linear_team_id"),
                                slack_channel=integrations.get("slack_channel"),
                                evidence_url=evidence.get("diff_url"),
                                compliance_summary=compliance_summary,
                                change_detail_summary=change_summary,
                            )

        except Exception as e:
            logger.exception(f"[run={run_id}] Watch execution failed")
            await self.watch_service.update_run(run_id, status="failed", error_message=str(e))
            return {"run_id": run_id, "status": "failed", "error": str(e), "changes": 0}

        # Aggregate agent reasoning
        run_agent_thoughts = []
        run_agent_summary_parts = []
        for tr in task_results:
            thoughts = tr.get("agent_thoughts") or []
            if thoughts:
                run_agent_thoughts.append({
                    "target_name": tr.get("target_name", "unknown"),
                    "thoughts": thoughts,
                })
                for t in thoughts:
                    text = t.get("thought") or t.get("reasoning") or t.get("text") or ""
                    if isinstance(text, str) and text.strip():
                        run_agent_summary_parts.append(text.strip()[:200])

        run_agent_summary = None
        if run_agent_summary_parts:
            run_agent_summary = run_agent_summary_parts[0]
            if len(run_agent_summary_parts) > 1:
                run_agent_summary += " …"
        elif task_results:
            run_agent_summary = f"Completed {tasks_ok} target(s); {changes_count} change(s) detected."

        duration_ms = int((time.time() - start) * 1000)
        await self.watch_service.update_run(
            run_id,
            status="completed",
            completed_at=datetime.utcnow(),
            duration_ms=duration_ms,
            tasks_executed=tasks_ok,
            tasks_failed=tasks_fail,
            changes_detected=changes_count,
            agent_summary=run_agent_summary,
            agent_thoughts=run_agent_thoughts if run_agent_thoughts else None,
        )
        self.db.table("watches").update({"last_run_at": datetime.utcnow().isoformat()}).eq("id", watch_id).execute()
        logger.info(f"[run={run_id}] Completed: {tasks_ok} ok, {tasks_fail} failed, {changes_count} changes")
        return {"run_id": run_id, "status": "completed", "changes": changes_count}

    # ── Agentic harness ───────────────────────────────────────────────

    async def _run_agentic_harness(self, watch: Dict[str, Any], run_id: str) -> List[Dict[str, Any]]:
        """Run main Claude agent; it spawns browser-use subagents via tool calls."""

        async def spawn_handler(tool_input: Dict[str, Any]) -> Dict[str, Any]:
            task = BrowserTask(
                id=tool_input.get("task_id", "unknown"),
                target_name=tool_input.get("target_name", "unknown"),
                task_description=tool_input.get("task_description", ""),
                starting_url=tool_input.get("starting_url"),
                search_query=tool_input.get("search_query"),
                extraction_instructions=tool_input.get("extraction_instructions", "Extract the main content."),
            )
            try:
                result = await self.execute_browser_use_task(task)
                return _task_result(
                    task_id=task.id,
                    target_name=task.target_name,
                    status="success",
                    content=result.get("content", ""),
                    content_hash=result.get("content_hash", ""),
                    url=result.get("url", ""),
                    screenshot_url=result.get("screenshot_url"),
                    agent_thoughts=result.get("agent_thoughts"),
                )
            except Exception as e:
                logger.warning(f"[spawn] task={task.id} failed: {e}")
                return _task_result(
                    task_id=task.id,
                    target_name=task.target_name,
                    status="failed",
                    error=str(e),
                )

        return await run_main_agent_loop(
            watch=watch,
            run_id=run_id,
            spawn_handler=spawn_handler,
            max_turns=20,
        )

    async def _research_regulatory_change(
        self,
        watch: Dict[str, Any],
        change: Dict[str, Any],
        current_snapshot: Dict[str, Any],
        previous_snapshot: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Spawn up to 15 browser-use agents to research a detected regulatory change.

        Agents search for:
        - News articles about the change
        - Official guidance documents
        - Consulting firm analyses
        - Reuters/press releases
        - Industry commentary
        """
        client = self._get_anthropic()
        if not client:
            return []

        semantic_diff = change.get("semantic_diff") or {}
        regulation_title = watch.get("regulation_title") or watch.get("name", "Unknown")

        # Use Claude to generate research queries
        prompt = f"""A regulatory change has been detected in: {regulation_title}

CHANGE SUMMARY:
{semantic_diff.get('summary', 'Content has changed')}

IMPACT LEVEL: {semantic_diff.get('impact_level', 'medium')}

Generate 10-15 specific search queries to research this change. Find information from:
1. News articles (Reuters, Bloomberg, industry publications)
2. Official guidance documents and announcements
3. Legal analysis from consulting firms
4. Government press releases
5. Industry expert commentary

Each query should target a specific aspect or source. Return ONLY a JSON array of queries (no markdown):
[
  "query 1",
  "query 2",
  ...
]"""

        try:
            response = client.messages.create(
                model=self.config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=2048,
                temperature=0.5,
                messages=[{"role": "user", "content": prompt}],
                system="You are a research expert. Return only the JSON array.",
            )
            text = response.content[0].text if response.content else "[]"
            queries = self._parse_json_from_text(text)
            if isinstance(queries, dict) and "queries" in queries:
                queries = queries["queries"]
            if not isinstance(queries, list):
                queries = []
        except Exception:
            logger.exception("Failed to generate research queries")
            queries = [
                f"{regulation_title} regulatory change news",
                f"{regulation_title} amendment analysis",
                f"{regulation_title} compliance guidance",
            ]

        # Spawn browser agents for each query (up to 15)
        queries = queries[:15]
        logger.info(f"Spawning {len(queries)} research agents")

        async def research_one(query: str, index: int) -> Dict[str, Any]:
            task = BrowserTask(
                id=f"research-{index}",
                target_name=f"Research: {query[:50]}",
                task_description=f"Research this regulatory change: {query}",
                search_query=query,
                extraction_instructions="Extract key information about the regulatory change, its implications, expert analysis, and context.",
            )
            try:
                result = await self.execute_browser_use_task(task)
                return {
                    "query": query,
                    "content": result.get("content", ""),
                    "url": result.get("url", ""),
                    "summary": result.get("content", "")[:500],
                }
            except Exception as e:
                logger.warning(f"Research agent {index} failed: {e}")
                return {"query": query, "content": "", "url": "", "error": str(e)}

        findings = await asyncio.gather(*[research_one(q, i) for i, q in enumerate(queries)])
        # Filter out failed/empty results
        findings = [f for f in findings if f.get("content")]
        logger.info(f"Completed research: {len(findings)}/{len(queries)} agents succeeded")
        return findings

    # ── Previous snapshot helper ──────────────────────────────────────

    async def _get_previous_snapshot(self, watch_id: str, current_run_id: str, target_name: str) -> Optional[Dict[str, Any]]:
        """Get the most recent snapshot for this watch+target from a PREVIOUS run (not the current one)."""
        r = (
            self.db.table("snapshots")
            .select("*")
            .eq("watch_id", watch_id)
            .eq("target_name", target_name)
            .neq("run_id", current_run_id)
            .order("captured_at", desc=True)
            .limit(1)
            .execute()
        )
        return r.data[0] if r.data else None

    # ── Execution plan ────────────────────────────────────────────────

    async def create_execution_plan(self, watch: Dict[str, Any], run_id: str) -> ExecutionPlan:
        """Use Claude to build execution plan from watch config."""
        config = watch.get("config") or {}
        targets = config.get("targets") or []
        if not targets:
            targets = [
                {
                    "name": watch.get("name", "default"),
                    "description": watch.get("description") or watch.get("name", ""),
                    "search_query": watch.get("name", ""),
                    "extraction_instructions": "Extract the main text content of the regulation or policy.",
                }
            ]

        client = self._get_anthropic()
        if not client:
            return self._plan_from_targets(watch["id"], run_id, targets)

        prompt = f"""You are a compliance monitoring expert. Given this watch configuration,
create a detailed execution plan for browser automation agents.

Watch name: {watch.get('name', 'Unnamed')}
Watch description: {watch.get('description', '')}
Watch config:
{json.dumps(config, indent=2)}

For each target to monitor, create a specific task with:
1. id: short unique id (e.g. target-0, target-1)
2. target_name: display name
3. task_description: detailed instructions for a browser agent — what to search for and what page to navigate to
4. starting_url: a specific URL to start from (use the most authoritative government/official source). Use Google if unsure.
5. search_query: what to search for if no direct URL
6. extraction_instructions: what content to extract from the page
7. fallback_strategy: alternative approach if the primary one fails

Return ONLY valid JSON in this exact shape (no markdown fences):
{{
  "tasks": [
    {{
      "id": "target-0",
      "target_name": "...",
      "task_description": "...",
      "starting_url": "https://...",
      "search_query": "...",
      "extraction_instructions": "...",
      "fallback_strategy": "..."
    }}
  ],
  "estimated_duration": 120
}}"""
        try:
            response = client.messages.create(
                model=self.config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=4096,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance automation expert. Return only the JSON object, no other text or markdown fences.",
            )
            text = response.content[0].text if response.content else "{}"
            plan_data = self._parse_json_from_text(text)
            tasks = []
            for t in plan_data.get("tasks", []):
                try:
                    tasks.append(BrowserTask(**t))
                except Exception:
                    continue
            if tasks:
                return ExecutionPlan(
                    watch_id=str(watch["id"]),
                    run_id=run_id,
                    tasks=tasks,
                    estimated_duration=plan_data.get("estimated_duration", 60),
                )
        except Exception:
            logger.exception("Failed to create Claude execution plan, falling back to targets")

        return self._plan_from_targets(watch["id"], run_id, targets)

    def _plan_from_targets(self, watch_id: str, run_id: str, targets: List[Dict[str, Any]]) -> ExecutionPlan:
        """Build plan directly from watch targets when Claude is unavailable."""
        tasks = []
        for i, t in enumerate(targets):
            tasks.append(
                BrowserTask(
                    id=t.get("id") or f"target-{i}",
                    target_name=t.get("name", f"target-{i}"),
                    task_description=t.get("description", t.get("name", "")),
                    starting_url=t.get("starting_url"),
                    search_query=t.get("search_query", t.get("name", "")),
                    extraction_instructions=t.get("extraction_instructions", "Extract the main text content."),
                    fallback_strategy=t.get("fallback_strategy"),
                )
            )
        return ExecutionPlan(watch_id=str(watch_id), run_id=run_id, tasks=tasks, estimated_duration=60)

    # ── Task execution ────────────────────────────────────────────────

    async def execute_tasks_with_retries(self, plan: ExecutionPlan, run_id: str) -> List[Dict[str, Any]]:
        """Run all tasks concurrently with retries."""
        coros = [self.execute_single_task_with_retry(t, run_id) for t in plan.tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)
        out = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                task = plan.tasks[i] if i < len(plan.tasks) else None
                out.append(_task_result(
                    task_id=task.id if task else "unknown",
                    target_name=task.target_name if task else "unknown",
                    status="failed",
                    error=str(r),
                ))
            else:
                out.append(r)
        return out

    async def execute_single_task_with_retry(self, task: BrowserTask, run_id: str) -> Dict[str, Any]:
        """Execute one browser-use task with retries and self-healing."""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                result = await self.execute_browser_use_task(task)
                return _task_result(
                    task_id=task.id,
                    target_name=task.target_name,
                    status="success",
                    content=result.get("content", ""),
                    content_hash=result.get("content_hash", ""),
                    url=result.get("url", ""),
                    screenshot_url=result.get("screenshot_url"),
                    agent_thoughts=result.get("agent_thoughts"),
                )
            except Exception as e:
                logger.warning(f"[task={task.id}] Attempt {attempt+1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    # Last resort: try self-healing via Claude
                    adapted = await self.adapt_task(task, e)
                    if adapted:
                        try:
                            result = await self.execute_browser_use_task(adapted)
                            return _task_result(
                                task_id=task.id,
                                target_name=task.target_name,
                                status="success",
                                content=result.get("content", ""),
                                content_hash=result.get("content_hash", ""),
                                url=result.get("url", ""),
                                screenshot_url=result.get("screenshot_url"),
                                agent_thoughts=result.get("agent_thoughts"),
                            )
                        except Exception as e2:
                            return _task_result(task_id=task.id, target_name=task.target_name, status="failed", error=str(e2))
                    return _task_result(task_id=task.id, target_name=task.target_name, status="failed", error=str(e))
                await asyncio.sleep(2 ** attempt)

        return _task_result(task_id=task.id, target_name=task.target_name, status="failed", error="Max retries exceeded")

    async def execute_browser_use_task(self, task: BrowserTask) -> Dict[str, Any]:
        """Run one task with browser-use Agent + cloud browser."""
        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the extracted compliance content to return")
        async def save_content(content: str) -> ActionResult:
            extracted_data["content"] = content
            return ActionResult(extracted_content=content)

        # Build the agent task prompt
        nav = ""
        if task.starting_url:
            nav = f"Go to {task.starting_url}"
        elif task.search_query:
            nav = f'Search Google for: "{task.search_query}"'
        else:
            nav = f'Search Google for: "{task.target_name}"'

        task_prompt = f"""{task.task_description}

Target: {task.target_name}

Steps:
1. {nav}
2. Navigate to the most relevant official/authoritative page
3. {task.extraction_instructions}
4. Use the save_content action to save the full text you extracted.

Important: Extract ALL relevant compliance/regulatory text. Be thorough."""

        use_cloud = bool(self.config.get("browser_use_api_key"))
        browser = Browser(headless=True, use_cloud=use_cloud)
        llm = ChatBrowserUse()

        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser,
            tools=tools,
            max_steps=30,
            use_vision="auto",
        )

        try:
            history = await agent.run()
        finally:
            # Ensure browser is closed
            try:
                await browser.close()
            except Exception:
                pass

        # Extract content — prefer our custom save_content action
        content = extracted_data.get("content", "")

        # Fallback: try final_result
        if not content:
            try:
                fr = history.final_result()
                if isinstance(fr, str) and fr.strip():
                    content = fr
                elif isinstance(fr, dict) and fr.get("content"):
                    content = fr["content"]
            except Exception:
                pass

        # Fallback: try extracted_content (returns list of strings)
        if not content:
            try:
                ec = history.extracted_content()
                if ec:
                    # Filter out None and empty strings
                    parts = [str(x) for x in ec if x]
                    content = "\n".join(parts)
            except Exception:
                pass

        content = content.strip() or "No content extracted."
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Extract URL
        url = ""
        try:
            urls = history.urls()
            if urls:
                url = urls[-1] if isinstance(urls[-1], str) else ""
        except Exception:
            pass

        # Screenshots — browser-use returns base64 strings, not URLs
        # For now, skip storing base64 screenshots (they're huge)
        screenshot_url = None

        # Agent reasoning
        agent_thoughts = self._serialize_model_thoughts(history)

        return {
            "content": content,
            "content_hash": content_hash,
            "url": url,
            "screenshot_url": screenshot_url,
            "agent_thoughts": agent_thoughts,
        }

    # ── Self-healing ──────────────────────────────────────────────────

    async def adapt_task(self, task: BrowserTask, error: Exception) -> Optional[BrowserTask]:
        """Use Claude to suggest an alternative task config after failure."""
        client = self._get_anthropic()
        if not client:
            return None

        prompt = f"""This browser automation task failed:

Task: {task.task_description}
Target: {task.target_name}
Starting URL: {task.starting_url}
Search Query: {task.search_query}
Error: {str(error)}

Suggest ONE alternative approach. Return ONLY valid JSON:
{{
  "task_description": "...",
  "starting_url": "https://...",
  "search_query": "...",
  "extraction_instructions": "..."
}}
If no viable alternative, return {{}}.
"""
        try:
            response = client.messages.create(
                model=self.config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=2048,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance automation expert. Return only JSON.",
            )
            text = response.content[0].text if response.content else "{}"
            adapted = self._parse_json_from_text(text)
            if not adapted or not adapted.get("task_description"):
                return None
            return BrowserTask(
                id=task.id,
                target_name=task.target_name,
                task_description=adapted.get("task_description", task.task_description),
                starting_url=adapted.get("starting_url") or task.starting_url,
                search_query=adapted.get("search_query") or task.search_query,
                extraction_instructions=adapted.get("extraction_instructions", task.extraction_instructions),
                fallback_strategy=task.fallback_strategy,
            )
        except Exception:
            logger.exception("adapt_task failed")
            return None

    # ── Helpers ────────────────────────────────────────────────────────

    def _serialize_model_thoughts(self, history: Any) -> List[Dict[str, Any]]:
        """Extract agent reasoning from browser-use history."""
        try:
            thoughts = history.model_thoughts() or []
        except Exception:
            return []
        out = []
        for t in thoughts:
            if isinstance(t, dict):
                out.append(t)
            elif hasattr(t, "__dict__"):
                d = {}
                for k, v in t.__dict__.items():
                    if not k.startswith("_"):
                        try:
                            json.dumps(v)
                            d[k] = v
                        except (TypeError, ValueError):
                            d[k] = str(v)
                out.append(d)
            else:
                out.append({"text": str(t)})
        return out

    def _parse_json_from_text(self, text: str) -> Dict[str, Any]:
        """Extract JSON object from text that may contain markdown fences or prose."""
        text = text.strip()
        # Strip markdown code fences
        if "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                text = match.group(1).strip()
        # Find the JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {}

    # ── Mock fallback ─────────────────────────────────────────────────

    async def _execute_mock_tasks(
        self,
        watch_id: str,
        run_id: str,
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Mock task execution when browser-use is not available."""
        results = []
        for i, t in enumerate(targets):
            name = t.get("name", f"target-{i}")
            content = f"[MOCK] Content for {name}. Install browser-use and set BROWSER_USE_API_KEY for real monitoring."
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            results.append(_task_result(
                task_id=t.get("id", f"target-{i}"),
                target_name=name,
                status="success",
                content=content,
                content_hash=content_hash,
                url="https://example.com/mock",
            ))
        return results
