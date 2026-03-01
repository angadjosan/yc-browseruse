"""Agent harness: main Claude agent with spawn_browser_agent tool.

The main agent runs in an agentic loop. It decides when to spawn browser-use
subagents via the spawn_browser_agent tool — no hardcoded Python loops.
"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.config import get_config

logger = logging.getLogger(__name__)

# Tool definition for Anthropic API
SPAWN_BROWSER_AGENT_TOOL = {
    "name": "spawn_browser_agent",
    "description": (
        "Spawn a browser-use subagent to complete a web task. Each call starts a new browser session. "
        "Use this for each target/page you need to monitor or extract content from. "
        "You may spawn multiple agents in parallel for different targets. "
        "Spawn at most 5 agents per run — pick the most important targets only."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "Short unique id for this task (e.g. target-0, target-1)",
            },
            "target_name": {
                "type": "string",
                "description": "Display name for the target (e.g. GDPR Article 25, Vendor ToS)",
            },
            "task_description": {
                "type": "string",
                "description": "Detailed instructions for the browser agent — what to search for and what page to navigate to",
            },
            "starting_url": {
                "type": "string",
                "description": "Optional specific URL to start from. Use the most authoritative government/official source.",
            },
            "search_query": {
                "type": "string",
                "description": "What to search for if no direct URL (e.g. Google search)",
            },
            "extraction_instructions": {
                "type": "string",
                "description": "What content to extract from the page (regulatory text, policy sections, etc.)",
            },
        },
        "required": ["task_id", "target_name", "task_description", "extraction_instructions"],
    },
}


def _build_system_prompt(watch: Dict[str, Any]) -> str:
    return """You are a compliance monitoring orchestrator. Your job is to spawn browser-use subagents to monitor regulatory and vendor policy pages.

You have one tool: spawn_browser_agent. Each call spawns a new browser session (subagent) that navigates the web and extracts content.

Your workflow:
1. Analyze the watch configuration and targets
2. For each target to monitor, call spawn_browser_agent with task_id, target_name, task_description, starting_url (if known), search_query, and extraction_instructions
3. You may spawn at most 5 agents — pick the highest-priority targets
4. Each subagent runs independently; you can reason about which targets need coverage based on the watch config
5. When you have spawned agents for all relevant targets, summarize and finish

Important:
- Call spawn_browser_agent for EACH distinct target/page you want monitored. Do not skip targets.
- Provide clear, specific task_description and extraction_instructions so subagents succeed
- If a target has a known URL, use starting_url. Otherwise use search_query
- When done spawning, provide a brief summary of what was monitored
"""


def _build_user_prompt(watch: Dict[str, Any], run_id: str) -> str:
    config = watch.get("config") or {}
    return f"""Run a compliance monitoring pass for this watch.

Watch name: {watch.get('name', 'Unnamed')}
Watch description: {watch.get('description', '')}
Run ID: {run_id}

Watch config:
{json.dumps(config, indent=2)}

Spawn browser agents for each target that needs to be monitored. Extract regulatory/policy content from the pages. Call spawn_browser_agent for each target, then summarize when complete.
"""


async def run_main_agent_loop(
    watch: Dict[str, Any],
    run_id: str,
    spawn_handler: Callable[[Dict[str, Any]], Any],
    max_turns: int = 20,
) -> List[Dict[str, Any]]:
    """Run the main Claude agent in an agentic loop. Returns task results from spawn_browser_agent calls."""
    config = get_config()
    client = None
    if config.get("anthropic_api_key"):
        from anthropic import Anthropic
        client = Anthropic(api_key=config["anthropic_api_key"])
    if not client:
        raise RuntimeError("ANTHROPIC_API_KEY required for agent harness")

    tools = [SPAWN_BROWSER_AGENT_TOOL]
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": _build_user_prompt(watch, run_id)},
    ]
    task_results: List[Dict[str, Any]] = []
    model = config.get("claude_model", "claude-sonnet-4-20250514")

    for turn in range(max_turns):
        response = client.messages.create(
            model=model,
            max_tokens=8192,
            system=_build_system_prompt(watch),
            messages=messages,
            tools=tools,
            tool_choice={"type": "auto"},
        )

        # Check stop reason
        stop_reason = getattr(response, "stop_reason", None) or response.stop_reason
        if stop_reason == "end_turn":
            # No more tool use; agent is done
            break

        # Collect tool use blocks
        tool_calls: List[tuple] = []  # (tool_id, tool_name, tool_input, block)
        for block in response.content:
            if isinstance(block, dict):
                block_type = block.get("type")
            else:
                block_type = getattr(block, "type", None)

            if block_type == "tool_use":
                tool_id = block.get("id") if isinstance(block, dict) else getattr(block, "id", "")
                tool_name = block.get("name") if isinstance(block, dict) else getattr(block, "name", "")
                tool_input = block.get("input") if isinstance(block, dict) else getattr(block, "input", {})
                if isinstance(tool_input, str):
                    try:
                        tool_input = json.loads(tool_input)
                    except json.JSONDecodeError:
                        tool_input = {}
                tool_calls.append((tool_id, tool_name, tool_input, block))

        if not tool_calls:
            break

        # Execute tool calls (parallel for spawn_browser_agent)
        async def run_one(tool_id: str, tool_name: str, tool_input: Dict[str, Any]) -> tuple:
            if tool_name == "spawn_browser_agent":
                try:
                    result = await spawn_handler(tool_input)
                    content_str = result.get("content", "") or ""
                    preview = content_str[:500] + ("..." if len(content_str) > 500 else "")
                    return (
                        tool_id,
                        json.dumps({
                            "status": result.get("status", "unknown"),
                            "target_name": result.get("target_name", ""),
                            "content_preview": preview or "(no content)",
                            "url": result.get("url", ""),
                            "error": result.get("error"),
                        }),
                        result,
                    )
                except Exception as e:
                    logger.exception(f"spawn_browser_agent failed: {e}")
                    return (
                        tool_id,
                        json.dumps({"status": "failed", "error": str(e)}),
                        {
                            "task_id": tool_input.get("task_id", "unknown"),
                            "target_name": tool_input.get("target_name", "unknown"),
                            "status": "failed",
                            "error": str(e),
                        },
                    )
            return (tool_id, json.dumps({"error": f"Unknown tool: {tool_name}"}), None)

        results = await asyncio.gather(*[run_one(tid, tname, tinput) for tid, tname, tinput, _ in tool_calls])
        for (tool_id, content, result) in results:
            if result:
                task_results.append(result)
        tool_result_blocks = [{"type": "tool_result", "tool_use_id": tid, "content": c} for tid, c, _ in results]

        # Append assistant message and our tool results
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_result_blocks})
        # Keep message history bounded to avoid token overflow.
        # Retain: initial user prompt + last 6 assistant/user pairs.
        if len(messages) > 13:
            messages = [messages[0]] + messages[-12:]

    return task_results
