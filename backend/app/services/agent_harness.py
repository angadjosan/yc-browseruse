"""Agent harness: main Claude agent with spawn_browser_agent tool.

The main agent runs in an agentic loop. It decides when to spawn browser-use
subagents via the spawn_browser_agent tool — no hardcoded Python loops.
"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from app.config import get_config
from app.prompts import load_prompt

logger = logging.getLogger(__name__)

# Tool definition for Anthropic API
SPAWN_BROWSER_AGENT_TOOL = {
    "name": "spawn_browser_agent",
    "description": (
        "Spawn a browser-use subagent to navigate the web and extract regulatory text. "
        "Each call starts an independent cloud browser session. "
        "Maximum 4 agents per run (1 primary + 3 secondary). "
        "Provide precise task_description and extraction_instructions for best results."
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
    return load_prompt("orchestrator_system")


def _build_user_prompt(watch: Dict[str, Any], run_id: str) -> str:
    config = watch.get("config") or {}
    return load_prompt(
        "orchestrator_user",
        watch_name=watch.get("name", "Unnamed"),
        watch_description=watch.get("description", ""),
        run_id=run_id,
        watch_config=json.dumps(config, indent=2),
    )


async def run_main_agent_loop(
    watch: Dict[str, Any],
    run_id: str,
    spawn_handler: Callable[[Dict[str, Any]], Any],
    max_turns: int = 10,
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
