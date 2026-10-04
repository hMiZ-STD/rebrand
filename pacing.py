"""
Pacing and human behavior simulation module.
Provides randomized delays, natural scrolling, and coffee breaks
to emulate organic user interactions and minimize detection risk.
"""
import asyncio
import logging
import random
import time
from typing import Tuple

import config

logger = logging.getLogger("insta_unlike")


def get_random_delay(min_val: float, max_val: float) -> float:
    """Generate a naturally distributed delay between min and max."""
    mean = (min_val + max_val) / 2.0
    sigma = (max_val - min_val) / 6.0  # 99.7% of values fall within [min, max]
    delay = random.gauss(mean, sigma)
    return max(min_val, min(max_val, delay))


async def sleep_human(min_s: float, max_s: float, reason: str = "") -> None:
    """Asynchronous sleep with human jitter."""
    duration = get_random_delay(min_s, max_s)
    if reason:
        logger.debug(f"Pacing: sleeping {duration:.2f}s ({reason})")
    await asyncio.sleep(duration)


async def click_delay() -> None:
    """Short delay between individual post checkbox selections."""
    await sleep_human(config.CLICK_DELAY_MIN, config.CLICK_DELAY_MAX, "click delay")


async def batch_cooldown() -> None:
    """Cooldown pause between successive unlike batches."""
    duration = get_random_delay(config.BATCH_DELAY_MIN, config.BATCH_DELAY_MAX)
    logger.info(f"Batch completed. Cooling down for {duration:.1f}s...")
    await asyncio.sleep(duration)


def schedule_next_break(current_batch: int) -> int:
    """Determine which future batch triggers the next coffee break."""
    interval = random.randint(
        config.COFFEE_BREAK_EVERY_N_BATCHES_MIN,
        config.COFFEE_BREAK_EVERY_N_BATCHES_MAX
    )
    return current_batch + interval


async def take_coffee_break() -> None:
    """Longer pause to disrupt automation patterns."""
    duration = get_random_delay(config.COFFEE_BREAK_DURATION_MIN, config.COFFEE_BREAK_DURATION_MAX)
    mins = duration / 60.0
    logger.info(f"Taking human-like break for {mins:.1f} minutes ({duration:.0f}s)...")
    await asyncio.sleep(duration)
    logger.info("Break finished. Resuming automation.")


async def natural_scroll(page, distance: int = 500) -> None:
    """Smooth, jittered scroll to trigger virtualized DOM rendering."""
    steps = random.randint(4, 8)
    step_distance = distance / steps
    for _ in range(steps):
        # Add micro-variation
        variation = step_distance * random.uniform(0.8, 1.2)
        await page.mouse.wheel(0, variation)
        await asyncio.sleep(random.uniform(0.05, 0.15))
    await asyncio.sleep(random.uniform(0.3, 0.7))
