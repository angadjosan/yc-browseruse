"""Claude-powered orchestrator: execution plans, browser-use agents, retries, self-healing, change detection.

Implements TECHNICAL_DESIGN.md: OrchestratorEngine creates execution plans via Claude,
assigns tasks to browser-use agents (with custom Tools), retries with adapt_task on failure.
"""
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import get_config
from app.db import get_supabase
from app.services.diff_engine import DiffEngine
from app.services.evidence_service import EvidenceService
from app.services.notification_hub import NotificationHub
from app.services.watch_service import WatchService


class BrowserTask(BaseModel):
    """Per-target browser task from orchestrator plan (TECHNICAL_DESIGN §2.1)."""
    id: str
    target_name: str
    task_description: str
    starting_url: Optional[str] = None
    search_query: Optional[str] = None
    extraction_instructions: str
    fallback_strategy: Optional[str] = None


class ExecutionPlan(BaseModel):
    """Claude-generated execution plan for a watch run (TECHNICAL_DESIGN §2.1)."""
    watch_id: str
    run_id: str
    tasks: List[BrowserTask]
    estimated_duration: int = 0  # seconds


def _task_result_to_dict(
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
    ts = int(time.time())
    out: Dict[str, Any] = {
        "task_id": task_id,
        "target_name": target_name,
        "status": status,
        "content": content,
        "content_hash": content_hash,
        "url": url,
        "screenshot_url": screenshot_url,
        "timestamp": ts,
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
            from browser_use import Agent, Browser, ChatBrowserUse
            return True
        except ImportError:
            return False

    def _has_anthropic(self) -> bool:
        return bool(self.config.get("anthropic_api_key"))

    def _generate_run_id(self) -> str:
        return str(uuid.uuid4())

    async def execute_watch(self, watch_id: str) -> Dict[str, Any]:
        """Main entry: load watch, create run, plan (Claude), execute tasks (browser-use or mock), diff, evidence, notify."""
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
                    "name": "default",
                    "description": watch.get("name", ""),
                    "search_query": watch.get("name", ""),
                    "extraction_instructions": "Extract main text content.",
                }
            ]

            if self._has_browser_use() and self._has_anthropic():
                plan = await self.create_execution_plan(watch, run_id)
                task_results = await self.execute_tasks_with_retries(plan, run_id)
            else:
                task_results = await self._execute_mock_tasks(watch_id, run_id, targets)

            for tr in task_results:
                if tr.get("status") == "success":
                    tasks_ok += 1
                else:
                    tasks_fail += 1

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
                previous = await self.watch_service.get_previous_snapshot(watch_id, target_name)
                if previous and str(previous.get("run_id")) == run_id:
                    prev_runs = await self.watch_service.get_watch_runs(watch_id, limit=2)
                    if len(prev_runs) >= 2:
                        old_run_id = str(prev_runs[1]["id"])
                        r2 = (
                            self.db.table("snapshots")
                            .select("*")
                            .eq("watch_id", watch_id)
                            .eq("target_name", target_name)
                            .eq("run_id", old_run_id)
                            .order("captured_at", desc=True)
                            .limit(1)
                            .execute()
                        )
                        previous = r2.data[0] if r2.data else None
                if previous:
                    change = await self.diff_engine.detect_changes(current_snapshot, previous)
                    if change.get("has_changes"):
                        changes_count += 1
                        change_row = {
                            "watch_id": watch_id,
                            "run_id": run_id,
                            "target_name": target_name,
                            "diff_summary": (change.get("semantic_diff") or {}).get("summary"),
                            "diff_details": {
                                "text_diff": change.get("text_diff"),
                                "semantic_diff": change.get("semantic_diff"),
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
                            )
        except Exception as e:
            await self.watch_service.update_run(run_id, status="failed", error_message=str(e))
            return {"run_id": run_id, "status": "failed", "error": str(e), "changes": 0}

        # Aggregate agent reasoning for run (AGENTS_BROWSERUSE: model_thoughts per task)
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
        return {"run_id": run_id, "status": "completed", "changes": changes_count}

    async def create_execution_plan(self, watch: Dict[str, Any], run_id: str) -> ExecutionPlan:
        """Use Claude to build execution plan from watch config (TECHNICAL_DESIGN §2.1)."""
        config = watch.get("config") or {}
        targets = config.get("targets") or []
        if not targets:
            targets = [
                {
                    "name": "default",
                    "description": watch.get("name", ""),
                    "search_query": watch.get("name", ""),
                    "extraction_instructions": "Extract the main text content.",
                }
            ]

        client = self._get_anthropic()
        if not client:
            return self._plan_from_targets(watch["id"], run_id, targets)

        prompt = f"""
You are a compliance monitoring expert. Given this watch configuration,
create a detailed execution plan for browser automation agents.

Watch name: {watch.get('name', 'Unnamed')}
Watch config:
{json.dumps(config, indent=2)}

For each target to monitor, create a specific task with:
1. id: short unique id (e.g. target-0, target-1)
2. target_name: display name
3. task_description: one sentence of what to do
4. starting_url: optional URL to start from, or null
5. search_query: what to search for (e.g. "GDPR Article 25")
6. extraction_instructions: what content to extract
7. fallback_strategy: optional alternative if primary fails

Return ONLY valid JSON in this exact shape (no markdown):
{{
  "tasks": [
    {{
      "id": "target-0",
      "target_name": "...",
      "task_description": "...",
      "starting_url": null,
      "search_query": "...",
      "extraction_instructions": "...",
      "fallback_strategy": null
    }}
  ],
  "estimated_duration": 120
}}
"""
        try:
            response = client.messages.create(
                model=self.config.get("claude_model", "claude-sonnet-4-20250514"),
                max_tokens=4096,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
                system="You are a compliance automation expert. Return only the JSON object, no other text.",
            )
            text = response.content[0].text if response.content else "{}"
            plan_data = self._parse_claude_plan(text)
            return ExecutionPlan(
                watch_id=str(watch["id"]),
                run_id=run_id,
                tasks=[BrowserTask(**t) for t in plan_data.get("tasks", [])],
                estimated_duration=plan_data.get("estimated_duration", 60),
            )
        except Exception:
            return self._plan_from_targets(watch["id"], run_id, targets)

    def _plan_from_targets(
        self, watch_id: str, run_id: str, targets: List[Dict[str, Any]]
    ) -> ExecutionPlan:
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

    def _parse_claude_plan(self, text: str) -> Dict[str, Any]:
        """Extract JSON plan from Claude response."""
        text = text.strip()
        for start in ("{", "\n{"):
            idx = text.find(start)
            if idx != -1:
                text = text[idx:]
                break
        for end_marker in ("}\n", "}"):
            last = text.rfind("}")
            if last != -1:
                text = text[: last + 1]
                break
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"tasks": [], "estimated_duration": 60}

    async def execute_tasks_with_retries(
        self, plan: ExecutionPlan, run_id: str
    ) -> List[Dict[str, Any]]:
        """Run all tasks with retries; return list of task result dicts (TECHNICAL_DESIGN §2.1)."""
        coros = [self.execute_single_task_with_retry(t, run_id) for t in plan.tasks]
        results = await asyncio.gather(*coros, return_exceptions=True)
        out = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                task = plan.tasks[i] if i < len(plan.tasks) else None
                name = task.target_name if task else "unknown"
                out.append(
                    _task_result_to_dict(
                        task_id=task.id if task else "unknown",
                        target_name=name,
                        status="failed",
                        error=str(r),
                    )
                )
            else:
                out.append(r)
        return out

    async def execute_single_task_with_retry(
        self, task: BrowserTask, run_id: str
    ) -> Dict[str, Any]:
        """Execute one task with retries and optional self-healing via adapt_task (TECHNICAL_DESIGN §2.1)."""
        max_retries = 3
        attempt = 0
        last_error = None

        while attempt < max_retries:
            try:
                result = await self.execute_browser_use_task(task)
                return _task_result_to_dict(
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
                last_error = e
                attempt += 1
                if attempt >= max_retries:
                    adapted = await self.adapt_task(task, e)
                    if adapted:
                        try:
                            result = await self.execute_browser_use_task(adapted)
                            return _task_result_to_dict(
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
                            return _task_result_to_dict(
                                task_id=task.id,
                                target_name=task.target_name,
                                status="failed",
                                error=str(e2),
                            )
                    return _task_result_to_dict(
                        task_id=task.id,
                        target_name=task.target_name,
                        status="failed",
                        error=str(e),
                    )
                await asyncio.sleep(2 ** attempt)

        return _task_result_to_dict(
            task_id=task.id,
            target_name=task.target_name,
            status="failed",
            error=str(last_error) if last_error else "Unknown error",
        )

    async def execute_browser_use_task(self, task: BrowserTask) -> Dict[str, Any]:
        """Run one task with browser-use Agent and custom save_content tool (TECHNICAL_DESIGN §2.1)."""
        from browser_use import Agent, Browser, ChatBrowserUse, Tools, ActionResult

        extracted_data: Dict[str, str] = {}
        tools = Tools()

        @tools.action("Save the extracted compliance content to return")
        async def save_content(content: str) -> ActionResult:
            extracted_data["content"] = content
            return ActionResult(extracted_content=content)

        nav = f"Search for: {task.search_query}" if task.search_query else (f"Navigate to: {task.starting_url}" if task.starting_url else "Search for the target.")
        task_prompt = f"""
{task.task_description}

Target: {task.target_name}

Instructions:
1. {nav}
2. {task.extraction_instructions}
3. Use the save_content action to save what you extract.
4. Take a screenshot of the final page if possible.

Be thorough and extract all relevant compliance information.
"""

        use_cloud = bool(self.config.get("browser_use_api_key"))
        browser = Browser(headless=True, use_cloud=use_cloud)
        llm = ChatBrowserUse()
        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser=browser,
            tools=tools,
            max_steps=50,
        )
        if hasattr(agent, "use_vision"):
            agent.use_vision = True

        history = await agent.run()

        content = extracted_data.get("content") or ""
        if not content and hasattr(history, "final_result"):
            fr = history.final_result()
            if isinstance(fr, dict) and "content" in fr:
                content = fr["content"]
            elif isinstance(fr, str):
                content = fr
        if not content and hasattr(history, "extracted_content"):
            content = history.extracted_content() or ""
        content = content or "No content extracted."

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        url = ""
        if hasattr(history, "urls") and callable(history.urls):
            urls = history.urls()
            url = urls[-1] if urls else ""
        screenshot_url = None
        if hasattr(history, "screenshots") and callable(history.screenshots):
            screens = history.screenshots()
            if screens:
                screenshot_url = screens[-1] if isinstance(screens[-1], str) else None

        # Capture agent reasoning (AGENTS_BROWSERUSE: history.model_thoughts())
        agent_thoughts = self._serialize_model_thoughts(history)

        return {
            "content": content,
            "content_hash": content_hash,
            "url": url,
            "screenshot_url": screenshot_url,
            "agent_thoughts": agent_thoughts,
        }

    async def adapt_task(self, task: BrowserTask, error: Exception) -> Optional[BrowserTask]:
        """Use Claude to suggest an alternative task config after failure (TECHNICAL_DESIGN §2.1)."""
        client = self._get_anthropic()
        if not client:
            return None

        prompt = f"""
This browser automation task failed:

Task: {task.task_description}
Target: {task.target_name}
Starting URL: {task.starting_url}
Search Query: {task.search_query}
Error: {str(error)}

Suggest ONE alternative approach. Return ONLY valid JSON:
{{
  "task_description": "...",
  "starting_url": null or "https://...",
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
            adapted = self._parse_task_adaptation(text)
            if not adapted:
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
            return None

    def _serialize_model_thoughts(self, history: Any) -> List[Dict[str, Any]]:
        """Extract agent reasoning from browser-use history (AGENTS_BROWSERUSE: model_thoughts())."""
        if not hasattr(history, "model_thoughts") or not callable(history.model_thoughts):
            return []
        try:
            thoughts = history.model_thoughts() or []
            out = []
            for t in thoughts:
                if isinstance(t, dict):
                    out.append(t)
                elif hasattr(t, "thought"):
                    out.append({"thought": getattr(t, "thought", str(t))})
                elif hasattr(t, "reasoning"):
                    out.append({"reasoning": getattr(t, "reasoning", str(t))})
                elif hasattr(t, "__dict__"):
                    out.append({k: v for k, v in t.__dict__.items() if not k.startswith("_")})
                else:
                    out.append({"text": str(t)})
            return out
        except Exception:
            return []

    def _parse_task_adaptation(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        for start in ("{", "\n{"):
            idx = text.find(start)
            if idx != -1:
                text = text[idx:]
                break
        last = text.rfind("}")
        if last != -1:
            text = text[: last + 1]
        try:
            data = json.loads(text)
            return data if data else None
        except json.JSONDecodeError:
            return None

    async def _execute_mock_tasks(
        self,
        watch_id: str,
        run_id: str,
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Mock task execution when browser-use or Anthropic is not configured."""
        results = []
        for i, t in enumerate(targets):
            name = t.get("name", f"target-{i}")
            content = f"Mock content for {name}. Configure BROWSER_USE_API_KEY and ANTHROPIC_API_KEY for real monitoring."
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            results.append(
                _task_result_to_dict(
                    task_id=t.get("id", f"target-{i}"),
                    target_name=name,
                    status="success",
                    content=content,
                    content_hash=content_hash,
                    url="https://example.com/mock",
                    screenshot_url=None,
                )
            )
        return results
