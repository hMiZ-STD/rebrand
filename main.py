"""
Instagram Bulk Unlike Automation - CLI Dispatcher & Orchestrator.

Modes:
  --login    : Open browser with persistent profile for manual one-time login & 2FA.
  --codegen  : Launch Playwright Inspector to interactively verify live DOM locators.
  --dry-run  : Navigate, enter select mode, select sample items, and cancel without unliking.
  --test [N] : Execute a single controlled test batch of N unlikes (default: 5).
  --run      : Full production execution respecting daily budgets, safety pacing, and breaks.
  --status   : Print current daily budget usage and baseline progress.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

import actions
import config
import guards
import pacing
import tracker

logger = tracker.setup_logging()


async def launch_browser(p, headless: bool = False):
    """Launch persistent Chromium context with anti-detection flags."""
    context = await p.chromium.launch_persistent_context(
        user_data_dir=str(config.USER_DATA_DIR),
        headless=headless,
        viewport={"width": config.VIEWPORT_WIDTH, "height": config.VIEWPORT_HEIGHT},
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
        locale="en-US",
    )
    page = context.pages[0] if context.pages else await context.new_page()
    return context, page


async def mode_login():
    """Step 1: One-time manual login in persistent browser window."""
    print("\n" + "=" * 60)
    print("  INSTAGRAM MANUAL LOGIN MODE")
    print("=" * 60)
    print("Opening browser with persistent profile at ./ig_profile...")
    print("Please log in with your credentials, complete 2FA, and verify your account.")

    async with async_playwright() as p:
        context, page = await launch_browser(p, headless=False)
        await page.goto("https://www.instagram.com/accounts/login/")

        print("\n>>> Keep this terminal open.")
        print(">>> Once logged in and on your home feed, press ENTER below to save session and exit.")
        await asyncio.to_thread(input, "\nPress [ENTER] when login is complete: ")

        # Quick verification
        if "/login" not in page.url:
            print("\n[SUCCESS] Session verified! Cookies and storage saved to ./ig_profile")
        else:
            print("\n[WARNING] Still on login page. You may need to run --login again if not finished.")

        await context.close()


def mode_codegen():
    """Launch Playwright codegen with persistent profile for selector discovery."""
    import subprocess
    cmd = [
        sys.executable,
        "-m",
        "playwright",
        "codegen",
        f"--user-data-dir={config.USER_DATA_DIR}",
        config.BASE_URL,
    ]
    print("\nLaunching Playwright Codegen Inspector...")
    print("Command:", " ".join(cmd))
    subprocess.run(cmd)


def print_status_summary(state_tracker: tracker.StateTracker):
    """Print high-level statistics table."""
    summary = state_tracker.get_progress_summary()
    print("\n" + "=" * 50)
    print("  INSTAGRAM UNLIKE PROGRESS SUMMARY")
    print("=" * 50)
    print(f"Date:                {state_tracker.state.get('date')}")
    print(f"Unliked Today:       {summary['unliked_today']} / {summary['daily_budget']}")
    print(f"Remaining Budget:    {state_tracker.remaining_today()}")
    print(f"All-Time Unliked:    {summary['total_unliked_all_time']}")
    print(f"Baseline Estimate:   {summary['baseline_total']}")
    print(f"Est. Remaining:      {summary['remaining_est']}")
    print("=" * 50 + "\n")


async def run_automation_loop(dry_run: bool = False, max_items: int = None):
    """Core batch processing loop."""
    state_tracker = tracker.StateTracker()
    print_status_summary(state_tracker)

    # Budget check
    if not dry_run and not state_tracker.can_proceed_today():
        logger.warning(
            f"Daily budget of {config.DAILY_BUDGET} unlikes reached for today! "
            "Please run again tomorrow to protect account safety."
        )
        return

    async with async_playwright() as p:
        context, page = await launch_browser(p, headless=config.HEADLESS)

        # 1. Navigate
        on_likes_page = await actions.navigate_to_likes(page)
        if not on_likes_page:
            logger.error("Could not access Likes page. Check login status with --login.")
            await context.close()
            return

        batch_number = 1
        stuck_counter = 0
        total_unliked_this_run = 0
        next_break_at = pacing.schedule_next_break(batch_number)

        # Calculate max limit for this run
        effective_limit = config.DAILY_BUDGET
        if max_items:
            effective_limit = max_items
        elif not dry_run:
            effective_limit = min(config.DAILY_BUDGET, state_tracker.remaining_today())

        logger.info(f"Target unlikes for this session: up to {effective_limit} items.")

        try:
            while total_unliked_this_run < effective_limit:
                # 2. Coffee break check
                if not dry_run and batch_number >= next_break_at:
                    await pacing.take_coffee_break()
                    next_break_at = pacing.schedule_next_break(batch_number)

                logger.info(f"\n--- Starting Batch #{batch_number} ---")

                # 3. Enter Select Mode
                entered_select = await actions.activate_select_mode(page)
                if not entered_select:
                    if await guards.is_empty_state(page):
                        logger.info("[COMPLETE] Done: No more liked posts found.")
                        break
                    stuck_counter += 1
                    if stuck_counter >= config.MAX_STUCK_BATCHES:
                        logger.warning(f"Could not enter select mode after {stuck_counter} attempts. Halting.")
                        break
                    await page.reload()
                    await actions.wait_for_page_ready(page)
                    continue

                # 4. Select Items Batch
                batch_target = min(config.MAX_BATCH_SIZE, effective_limit - total_unliked_this_run)
                selected = await actions.select_posts_batch(page, batch_target)

                if selected == 0:
                    logger.warning("No selectable posts found in this pass.")
                    stuck_counter += 1
                    if stuck_counter >= config.MAX_STUCK_BATCHES:
                        logger.info("Consecutive empty passes detected. Likely finished or stuck.")
                        break
                    await page.reload()
                    await actions.wait_for_page_ready(page)
                    continue

                stuck_counter = 0  # Reset stuck counter on progress

                # 5. Execute Unlike
                success, unliked = await actions.execute_unlike(page, dry_run=dry_run)
                if not success:
                    logger.error("Failed to complete batch unlike. Halting loop.")
                    break

                total_unliked_this_run += unliked
                if not dry_run:
                    state_tracker.record_unliked(unliked)

                # Progress output
                summary = state_tracker.get_progress_summary()
                status_prefix = "[DRY-RUN]" if dry_run else "[LIVE]"
                logger.info(
                    f"{status_prefix} Batch #{batch_number}: {unliked} unliked | "
                    f"Session: {total_unliked_this_run}/{effective_limit} | "
                    f"Today: {summary['unliked_today']}/{summary['daily_budget']} | "
                    f"Est. Left: {summary['remaining_est']}"
                )

                if total_unliked_this_run >= effective_limit:
                    logger.info(f"Target of {effective_limit} unlikes reached for this session.")
                    break

                # 6. Cooldown
                batch_number += 1
                await pacing.batch_cooldown()

        except KeyboardInterrupt:
            logger.info("\nExecution interrupted by user.")
        except Exception as e:
            logger.exception(f"Unexpected error in automation loop: {e}")
            await guards.capture_forensic_snapshot(page, prefix="error_crash")
        finally:
            logger.info("Gracefully finalizing session and ensuring all server requests have flushed...")
            try:
                await page.wait_for_timeout(4000)
            except Exception:
                pass
            await context.close()
            print_status_summary(state_tracker)


def main():
    parser = argparse.ArgumentParser(description="Instagram Bulk Unlike Automation")
    parser.add_argument("--login", action="store_true", help="Launch browser for 1-time manual login & 2FA")
    parser.add_argument("--codegen", action="store_true", help="Launch Playwright codegen for selector inspection")
    parser.add_argument("--dry-run", action="store_true", help="Run selection without unliking")
    parser.add_argument("--test", type=int, nargs="?", const=5, help="Test run of N unlikes (default: 5)")
    parser.add_argument("--run", action="store_true", help="Run full daily automation")
    parser.add_argument("--status", action="store_true", help="Show current state & daily quota")

    args = parser.parse_args()

    if args.login:
        asyncio.run(mode_login())
    elif args.codegen:
        mode_codegen()
    elif args.status:
        print_status_summary(tracker.StateTracker())
    elif args.dry_run:
        asyncio.run(run_automation_loop(dry_run=True, max_items=25))
    elif args.test is not None:
        asyncio.run(run_automation_loop(dry_run=False, max_items=args.test))
    elif args.run:
        asyncio.run(run_automation_loop(dry_run=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
