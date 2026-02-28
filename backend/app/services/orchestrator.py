"""Claude-powered orchestrator: execution plans, task execution (browser-use when available), retries, change detection."""
import asyncio
import hashlib
import time
from typing import Any, Dict, List, Optional

from app.config import get_config
from app.services.watch_service import WatchService
from app.services.diff_engine import DiffEngine
from app.services.evidence_service import EvidenceService
from app.services.notification_hub import NotificationHub
from app.db import get_supabase


class OrchestratorEngine:
    """Orchestrates watch execution: plan, run tasks (real or mock), diff, evidence, notify."""

    def __init__(self):
        self.config = get_config()
        self.watch_service = WatchService()
        self.diff_engine = DiffEngine()
        self.evidence_service = EvidenceService()
        self.notification_hub = NotificationHub()
        self._db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_supabase()
        return self._db

    def _has_browser_use(self) -> bool:
        return bool(self.config.get("browser_use_api_key"))

    def _has_anthropic(self) -> bool:
        return bool(self.config.get("anthropic_api_key"))

    async def execute_watch(self, watch_id: str) -> Dict[str, Any]:
        """Main entry: load watch, create run, execute tasks (real or mock), detect changes, evidence, notify."""
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
            # Get targets from watch config
            config = watch.get("config") or {}
            targets = config.get("targets") or [{"name": "default", "description": watch.get("name", ""), "search_query": watch.get("name", ""), "extraction_instructions": "Extract main text content."}]

            if self._has_browser_use() and self._has_anthropic():
                # Real execution with browser-use (optional integration)
                task_results = await self._execute_browser_tasks(watch_id, run_id, watch, targets)
            else:
                # Mock: create one snapshot per target with placeholder content
                task_results = await self._execute_mock_tasks(watch_id, run_id, targets)

            for tr in task_results:
                if tr.get("status") == "success":
                    tasks_ok += 1
                else:
                    tasks_fail += 1

            # Change detection per target
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
                # Previous snapshot might be the one we just inserted; get one from an older run
                if previous and str(previous.get("run_id")) == run_id:
                    prev_runs = await self.watch_service.get_watch_runs(watch_id, limit=2)
                    if len(prev_runs) >= 2:
                        old_run_id = str(prev_runs[1]["id"])
                        r2 = self.db.table("snapshots").select("*").eq("watch_id", watch_id).eq("target_name", target_name).eq("run_id", old_run_id).order("captured_at", desc=True).limit(1).execute()
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
                            "diff_details": {"text_diff": change.get("text_diff"), "semantic_diff": change.get("semantic_diff")},
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

        duration_ms = int((time.time() - start) * 1000)
        await self.watch_service.update_run(
            run_id,
            status="completed",
            completed_at=__import__("datetime").datetime.utcnow(),
            duration_ms=duration_ms,
            tasks_executed=tasks_ok,
            tasks_failed=tasks_fail,
            changes_detected=changes_count,
        )
        self.db.table("watches").update({"last_run_at": __import__("datetime").datetime.utcnow().isoformat()}).eq("id", watch_id).execute()
        return {"run_id": run_id, "status": "completed", "changes": changes_count}

    async def _execute_mock_tasks(
        self,
        watch_id: str,
        run_id: str,
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Mock task execution when browser-use is not configured."""
        results = []
        for i, t in enumerate(targets):
            name = t.get("name", f"target-{i}")
            content = f"Mock content for {name}. Configure BROWSER_USE_API_KEY and ANTHROPIC_API_KEY for real monitoring."
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            results.append({
                "status": "success",
                "target_name": name,
                "content": content,
                "content_hash": content_hash,
                "url": "https://example.com/mock",
                "screenshot_url": None,
                "timestamp": int(time.time()),
                "captured_at": __import__("datetime").datetime.utcnow().isoformat(),
            })
        return results

    async def _execute_browser_tasks(
        self,
        watch_id: str,
        run_id: str,
        watch: Dict[str, Any],
        targets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Real execution using browser-use agents. Optional: only if library and keys are present."""
        try:
            from browser_use import Agent, Browser, ChatBrowserUse
        except ImportError:
            return await self._execute_mock_tasks(watch_id, run_id, targets)

        results = []
        for i, target in enumerate(targets):
            task_desc = target.get("description", target.get("name", ""))
            search_query = target.get("search_query", task_desc)
            extract_instructions = target.get("extraction_instructions", "Extract the main text content.")
            task_prompt = f"""
{task_desc}
Target: {target.get('name', 'target')}
1. Search for: {search_query}
2. {extract_instructions}
3. Capture the main text and take a screenshot if possible.
"""
            try:
                browser = Browser(headless=True)
                agent = Agent(
                    task=task_prompt,
                    llm=ChatBrowserUse(),
                    browser=browser,
                    max_steps=30,
                )
                history = await agent.run()
                content = (history.final_result() or {}).get("content", "") if hasattr(history, "final_result") and callable(history.final_result) else str(history)
                if not content and hasattr(history, "extracted_content"):
                    content = history.extracted_content() or ""
                content = content or "No content extracted."
                content_hash = hashlib.sha256(content.encode()).hexdigest()
                url = ""
                if hasattr(history, "urls") and callable(history.urls):
                    urls = history.urls()
                    url = urls[-1] if urls else ""
                results.append({
                    "status": "success",
                    "target_name": target.get("name", f"target-{i}"),
                    "content": content,
                    "content_hash": content_hash,
                    "url": url,
                    "screenshot_url": None,
                    "timestamp": int(time.time()),
                    "captured_at": __import__("datetime").datetime.utcnow().isoformat(),
                })
            except Exception as e:
                results.append({
                    "status": "failed",
                    "target_name": target.get("name", f"target-{i}"),
                    "error": str(e),
                    "content": "",
                    "content_hash": "",
                    "url": "",
                })
        return results
