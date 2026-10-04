"""
Guards module for defensive security, block detection, and popup handling.
Halts automation immediately if Instagram rate-limiting or security challenges are triggered.
"""
import datetime
import logging
from pathlib import Path
from typing import Tuple

import config
import selectors

logger = logging.getLogger("insta_unlike")


async def capture_forensic_snapshot(page, prefix: str = "incident") -> Path:
    """Save an immediate screenshot and URL details for incident investigation."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = config.SCREENSHOTS_DIR / f"{prefix}_{timestamp}.png"
    try:
        await page.screenshot(path=str(filepath), full_page=True)
        logger.warning(f"Saved forensic screenshot: {filepath}")
    except Exception as e:
        logger.error(f"Failed to capture screenshot: {e}")
    return filepath


async def dismiss_popups(page) -> bool:
    """Detect and dismiss common intrusive popups (e.g. 'Not Now', cookies, notifications)."""
    dismissed_any = False
    for pattern in selectors.DISMISS_POPUP_TEXTS:
        try:
            # Query buttons with text matching pattern
            btn = page.get_by_role("button", name=pattern).first
            if await btn.is_visible(timeout=400):
                logger.info(f"Dismissing overlay popup: '{pattern.pattern}'")
                await btn.click(timeout=1000)
                dismissed_any = True
                await page.wait_for_timeout(400)
        except Exception:
            continue
    return dismissed_any


async def check_block_or_restriction(page) -> Tuple[bool, str]:
    """
    Examine the page URL and visible DOM text for any signs of rate limiting,
    action blocks, or authentication challenges.
    Returns (True, reason) if a block is detected, otherwise (False, "").
    """
    # 1. Check URL anomalies
    current_url = page.url.lower()
    for challenge in selectors.CHALLENGE_URL_PARTS:
        if challenge in current_url:
            reason = f"Security checkpoint or login redirect detected in URL: {page.url}"
            await capture_forensic_snapshot(page, prefix="block_url")
            return True, reason

    # 2. Check modal dialogs and body text for restriction keywords
    try:
        # Check text in dialogs first (Instagram usually presents action blocks in a modal)
        dialogs = page.locator(selectors.DIALOG_SELECTOR)
        dialog_count = await dialogs.count()
        for i in range(dialog_count):
            dialog = dialogs.nth(i)
            if await dialog.is_visible():
                dialog_text = await dialog.inner_text()
                for signature in selectors.BLOCK_SIGNATURES:
                    if signature.lower() in dialog_text.lower():
                        reason = f"Action block modal detected: '{signature}'"
                        await capture_forensic_snapshot(page, prefix="block_modal")
                        return True, reason

        # Check general page body text for blocks
        body_text = await page.locator("body").inner_text()
        for signature in selectors.BLOCK_SIGNATURES:
            if signature.lower() in body_text.lower():
                # Avoid false positives if "Something went wrong" is part of innocuous text
                if signature == "Something went wrong" and "retry" not in body_text.lower():
                    continue
                reason = f"Action restriction text detected: '{signature}'"
                await capture_forensic_snapshot(page, prefix="block_text")
                return True, reason

    except Exception as e:
        logger.debug(f"Block check encountered minor error: {e}")

    return False, ""


async def is_empty_state(page) -> bool:
    """Check if the Likes list has reached 0 remaining items."""
    try:
        body_text = await page.locator("body").inner_text()
        for signature in selectors.EMPTY_STATE_SIGNATURES:
            if signature.lower() in body_text.lower():
                return True
    except Exception:
        pass
    return False
