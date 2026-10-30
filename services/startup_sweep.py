"""
Wire the expiry sweep into FastAPI startup + optional background loop.

Drop the relevant pieces into main.py.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

logger = logging.getLogger(__name__)

# How often the background task re-runs (seconds). 24 h = 86400
SWEEP_INTERVAL_SECONDS = int(__import__("os").getenv("SWEEP_INTERVAL_SECONDS", "86400"))


async def run_sweep_once(get_data_fn: Callable, sweep_fn: Callable) -> None:
    """Fetch current ledger/content/passports and run the sweep."""
    try:
        ledger, content_items, passports = get_data_fn()
        summary = sweep_fn(ledger, content_items, passports)
        logger.info("Startup/cron sweep finished: %s", summary)
    except Exception:
        logger.exception("Expiry sweep failed")


async def sweep_background_loop(get_data_fn: Callable, sweep_fn: Callable) -> None:
    """Infinite loop for local / self-hosted deployments."""
    while True:
        await run_sweep_once(get_data_fn, sweep_fn)
        await asyncio.sleep(SWEEP_INTERVAL_SECONDS)


def register_startup_hooks(app, get_data_fn: Callable, sweep_fn: Callable) -> None:
    """
    Call this once from main.py after creating the FastAPI app.

    Example:
        from services.startup_sweep import register_startup_hooks
        from services.impact import sweep_expired

        def get_data():
            # return live lists from your DB / in-memory store
            return ledger, content_items, passports

        register_startup_hooks(app, get_data, sweep_expired)
    """

    @app.on_event("startup")
    async def _on_startup() -> None:
        # Run once immediately so the process never starts with stale flags
        await run_sweep_once(get_data_fn, sweep_fn)
        # Then keep running in the background (or rely on an external cron)
        asyncio.create_task(sweep_background_loop(get_data_fn, sweep_fn))
        logger.info(
            "Expiry sweep registered (interval=%ss)", SWEEP_INTERVAL_SECONDS
        )
