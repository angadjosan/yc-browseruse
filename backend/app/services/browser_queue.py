"""
Global semaphore to limit concurrent browser-use agents to BROWSER_CONCURRENCY_LIMIT.

All browser-use agent.run() calls must go through `run_browser_agent()` so that
at most 25 browser sessions are active at the same time. Tasks beyond that limit
are queued automatically by asyncio.Semaphore.

Usage:
    from app.services.browser_queue import run_browser_agent

    history = await asyncio.wait_for(
        run_browser_agent(agent.run(max_steps=3)),
        timeout=300.0,
    )
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

BROWSER_CONCURRENCY_LIMIT = 25

_browser_semaphore = asyncio.Semaphore(BROWSER_CONCURRENCY_LIMIT)


async def run_browser_agent(coro):
    """Acquire the global browser semaphore, then await *coro*.

    The semaphore limits concurrent browser-use agents to
    BROWSER_CONCURRENCY_LIMIT (25). Callers beyond that are queued and
    resume automatically once a slot frees up.

    The timeout (if any) should wrap this call so it applies only to the
    actual agent run, not the queue wait:

        await asyncio.wait_for(run_browser_agent(agent.run(...)), timeout=N)
    """
    slot = _browser_semaphore._value  # for logging only — not authoritative
    if slot == 0:
        logger.info(
            "browser_queue: all %d slots occupied — queuing browser agent",
            BROWSER_CONCURRENCY_LIMIT,
        )
    async with _browser_semaphore:
        logger.debug(
            "browser_queue: acquired slot (%d remaining)",
            _browser_semaphore._value,
        )
        return await coro
