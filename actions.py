"""
Core action automation engine for Instagram's 'Your Activity' Likes page.
Handles page readiness, selection mode activation, dynamic batch selection,
executing unlikes with modal confirmation, and waiting for server-side deletion to settle.
"""
import asyncio
import logging
import re
import time
from typing import List, Optional, Tuple

from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeoutError

import config
import guards
import pacing
import selectors

logger = logging.getLogger("insta_unlike")


async def wait_for_page_ready(page: Page, timeout_ms: int = 35000) -> bool:
    """
    Wait for Instagram's React bundle, GraphQL queries, and likes grid to finish loading.
    Eliminates race conditions where elements are queried before content settles.
    """
    logger.info("Waiting for page content and network to settle...")

    # 1. Wait for network idle (with fallback)
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        logger.debug("Networkidle timeout hit; proceeding to element checks...")

    # 2. Wait for loading spinners to disappear
    try:
        spinner = page.locator(selectors.SPINNER_SELECTOR).first
        if await spinner.is_visible(timeout=1000):
            logger.debug("Waiting for loading spinner to disappear...")
            await spinner.wait_for(state="hidden", timeout=20000)
    except Exception:
        pass

    # 3. Wait for primary UI anchor: either 'Select' button, post tiles, or empty state
    try:
        select_locator = page.locator(selectors.SELECT_TRIGGER).first
        await select_locator.wait_for(state="visible", timeout=timeout_ms)
        logger.info("Likes page is ready and interactive.")
        return True
    except PlaywrightTimeoutError:
        # Check if it's already an empty state
        if await guards.is_empty_state(page):
            logger.info("Page loaded: Empty state confirmed (no likes).")
            return True
        logger.warning("Timed out waiting for 'Select' element to appear.")
        return False


async def navigate_to_likes(page: Page) -> bool:
    """
    Navigate to the likes activity page, dismiss overlays, and ensure content is ready.
    Returns True if successfully on the likes page, False if redirected or blocked.
    """
    logger.info(f"Navigating to {config.BASE_URL}...")
    try:
        await page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=config.PAGE_TIMEOUT_MS)
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return False

    # Check for authentication redirect
    if "/accounts/login" in page.url or "/login" in page.url:
        logger.error("Session expired or not logged in! Redirected to login page.")
        return False

    # Dismiss common popups
    await guards.dismiss_popups(page)

    # Check for account block or challenge
    is_blocked, reason = await guards.check_block_or_restriction(page)
    if is_blocked:
        logger.critical(f"HALTING: {reason}")
        return False

    # Wait for page content to fully load
    ready = await wait_for_page_ready(page)
    return ready


async def is_select_mode_active(page: Page) -> bool:
    """Check if selection mode is currently active (e.g. Cancel trigger is present)."""
    cancel_el = page.locator(selectors.CANCEL_TRIGGER).first
    try:
        return await cancel_el.is_visible(timeout=500)
    except Exception:
        return False


async def activate_select_mode(page: Page) -> bool:
    """
    Click the 'Select' button to enter bulk selection mode.
    Returns True if select mode is activated or already active.
    """
    if await is_select_mode_active(page):
        return True

    # Check for empty state first
    if await guards.is_empty_state(page):
        logger.info("Empty state detected: No liked posts remain.")
        return False

    select_el = page.locator(selectors.SELECT_TRIGGER).first
    try:
        await select_el.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
        logger.info("Clicking 'Select' button to enter selection mode...")
        await select_el.click()

        # Wait for Cancel or Selection toolbar to confirm mode activation
        cancel_el = page.locator(selectors.CANCEL_TRIGGER).first
        await cancel_el.wait_for(state="visible", timeout=6000)
        await page.wait_for_timeout(500)
        return True
    except Exception as e:
        logger.warning(f"Could not enter select mode: {e}")

    return False


async def cancel_select_mode(page: Page) -> None:
    """Exit selection mode by clicking Cancel if visible."""
    try:
        cancel_el = page.locator(selectors.CANCEL_TRIGGER).first
        if await cancel_el.is_visible(timeout=500):
            await cancel_el.click()
            await page.wait_for_timeout(500)
    except Exception:
        pass


async def get_selected_count_from_ui(page: Page) -> int:
    """
    Extract the number of currently selected items from the toolbar (e.g. '1 selected' or '15 selected').
    """
    try:
        counter_el = page.locator('text=/\\d+\\s+selected/i').first
        if await counter_el.is_visible(timeout=300):
            text = await counter_el.inner_text()
            match = selectors.SELECTED_COUNT_PATTERN.search(text)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return 0


async def select_posts_batch(page: Page, target_batch_size: int) -> int:
    """
    Select up to target_batch_size posts with human-like delays.
    Scrolls smoothly to trigger virtualized DOM loading as needed.
    Returns the number of posts successfully selected.
    """
    selected_count = await get_selected_count_from_ui(page)
    scroll_attempts = 0
    max_scrolls = 8
    clicked_indices = set()

    while selected_count < target_batch_size and scroll_attempts < max_scrolls:
        # Find all visible post thumbnails currently rendered in the DOM
        tiles = page.locator(selectors.POST_TILE_IMAGES)
        total_tiles = await tiles.count()
        newly_clicked = 0

        for i in range(total_tiles):
            if selected_count >= target_batch_size:
                break
            if i in clicked_indices:
                continue

            tile = tiles.nth(i)
            try:
                if not await tile.is_visible():
                    continue

                # Click the post tile (or its clickable wrapper)
                await tile.click(timeout=2000)
                clicked_indices.add(i)
                newly_clicked += 1

                # Human micro-delay between clicks
                await pacing.click_delay()

                # Read verified UI counter
                ui_count = await get_selected_count_from_ui(page)
                if ui_count > selected_count:
                    selected_count = ui_count
                else:
                    selected_count += 1

            except Exception as e:
                logger.debug(f"Could not click tile {i}: {e}")
                continue

        # If we need more items, scroll down to trigger virtualized DOM lazy-loading
        if selected_count < target_batch_size:
            scroll_attempts += 1
            logger.debug(f"Scrolling to load more posts ({selected_count}/{target_batch_size} selected)...")
            await pacing.natural_scroll(page, distance=550)
            await page.wait_for_timeout(1000)

            # Check if block or restriction appeared during scrolling/clicking
            is_blocked, reason = await guards.check_block_or_restriction(page)
            if is_blocked:
                logger.critical(f"HALTING: Block detected during selection: {reason}")
                return selected_count

            # If scroll did not yield any new clickable elements, we may have reached the end of the grid
            if newly_clicked == 0 and scroll_attempts >= 3:
                logger.info("Reached end of selectable items in grid.")
                break

    # Read final verified UI count
    ui_count = await get_selected_count_from_ui(page)
    if ui_count > 0:
        selected_count = ui_count

    return selected_count


async def wait_for_unlike_settled(page: Page, timeout_seconds: int = 45) -> bool:
    """
    Intelligently wait for Instagram's servers to process the unlikes,
    dismiss dialogs, finish GraphQL mutation requests, and reload the grid.
    Accommodates arbitrary network delays so the browser is never closed prematurely.
    """
    logger.info("Waiting for Instagram server to process batch deletion...")
    start_time = time.time()

    # 1. Wait for confirmation dialog to be hidden
    try:
        dialog = page.locator(selectors.DIALOG_SELECTOR).first
        if await dialog.is_visible():
            await dialog.wait_for(state="hidden", timeout=20000)
            logger.debug("Modal dialog dismissed.")
    except Exception as e:
        logger.debug(f"Modal hide wait note: {e}")

    # 2. Wait for network requests to complete
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        logger.debug("Networkidle timeout hit after unlike; continuing DOM verification...")

    # 3. Wait for any loading spinners to detach
    try:
        spinner = page.locator(selectors.SPINNER_SELECTOR).first
        if await spinner.is_visible(timeout=1000):
            logger.debug("Waiting for post-unlike loading spinners to complete...")
            await spinner.wait_for(state="hidden", timeout=25000)
    except Exception:
        pass

    # 4. Poll until the page reflects completion:
    # Either selection toolbar resets, or new posts load, or empty state appears
    while (time.time() - start_time) < timeout_seconds:
        # Check if block occurred
        is_blocked, reason = await guards.check_block_or_restriction(page)
        if is_blocked:
            logger.critical(f"HALTING: Restriction detected after unlike: {reason}")
            return False

        # If empty state appeared, all likes are gone!
        if await guards.is_empty_state(page):
            logger.info("Instagram confirmed empty state: All likes unliked!")
            return True

        # Check if the selection toolbar ("X selected") has cleared
        selected_now = await get_selected_count_from_ui(page)
        if selected_now == 0:
            # Verified selection bar reset
            logger.info("Instagram confirmed: Batch deletion settled and grid refreshed.")
            return True

        await asyncio.sleep(1.0)

    logger.warning("Batch wait reached safety timeout. Proceeding...")
    return True


async def execute_unlike(page: Page, dry_run: bool = False) -> Tuple[bool, int]:
    """
    Trigger the Unlike action:
    1. Click the active primary 'Unlike' button in the toolbar.
    2. Wait explicitly for the visible confirmation dialog containing 'Unlike'.
    3. Click confirmation 'Unlike' button inside the dialog.
    4. Wait comprehensively for server processing, network settling, and grid update.
    If dry_run is True, cancels the selection instead of unliking.
    Returns (success, count_unliked).
    """
    selected_count = await get_selected_count_from_ui(page)
    approx_count = selected_count if selected_count > 0 else 1

    unlike_btn = page.locator(selectors.UNLIKE_TRIGGER).first
    try:
        await unlike_btn.wait_for(state="visible", timeout=config.ACTION_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        logger.error("Could not find active 'Unlike' toolbar action button.")
        return False, 0

    if dry_run:
        logger.info(f"[DRY-RUN] Selected {approx_count} posts. Cancelling selection without unliking.")
        await cancel_select_mode(page)
        return True, approx_count

    # 1. Click Unlike toolbar button
    logger.info(f"Clicking 'Unlike' for batch of {approx_count} posts...")
    await unlike_btn.click()
    await page.wait_for_timeout(800)

    # 2. Wait explicitly for the VISIBLE confirmation dialog
    dialog = page.locator(selectors.DIALOG_SELECTOR).first
    try:
        await dialog.wait_for(state="visible", timeout=8000)
    except PlaywrightTimeoutError:
        logger.error("Confirmation dialog did not appear. Halting to prevent desync.")
        await guards.capture_forensic_snapshot(page, prefix="no_dialog")
        return False, 0

    # 3. Click the confirmation 'Unlike' button inside the modal
    confirm_btn = page.locator(selectors.DIALOG_CONFIRM_UNLIKE).first
    try:
        await confirm_btn.wait_for(state="visible", timeout=4000)
        await confirm_btn.click()
        logger.info("Confirmed Unlike in modal dialog.")
    except Exception as e:
        logger.error(f"Failed to click modal confirmation button: {e}")
        await guards.capture_forensic_snapshot(page, prefix="modal_click_fail")
        return False, 0

    # 4. Wait for server-side deletion, GraphQL mutation, and grid re-rendering
    settled = await wait_for_unlike_settled(page, timeout_seconds=45)
    if not settled:
        return False, 0

    return True, approx_count
