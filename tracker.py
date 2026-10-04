"""
State tracking, daily quota enforcement, and append-only audit logging.
Maintains state in logs/state.json across runs.
"""
import datetime
import json
import logging
from pathlib import Path
from typing import Dict, Any

import config


class StateTracker:
    def __init__(self, state_file: Path = config.STATE_FILE):
        self.state_file = state_file
        self.state: Dict[str, Any] = self._load_state()

    def _get_today_str(self) -> str:
        return datetime.date.today().isoformat()

    def _load_state(self) -> Dict[str, Any]:
        today = self._get_today_str()
        default_state = {
            "date": today,
            "unliked_today": 0,
            "total_unliked_all_time": 0,
            "baseline_total": config.ESTIMATED_TOTAL_LIKES,
            "last_session": None,
        }

        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # If date changed, reset today's counter
                if data.get("date") != today:
                    data["date"] = today
                    data["unliked_today"] = 0
                return data
            except Exception as e:
                logging.getLogger("insta_unlike").warning(f"Could not read state.json: {e}. Using defaults.")

        return default_state

    def save(self) -> None:
        """Persist state to JSON file."""
        self.state["last_session"] = datetime.datetime.now().isoformat()
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def record_unliked(self, count: int) -> None:
        """Record a successful batch of unlikes."""
        self.state["unliked_today"] += count
        self.state["total_unliked_all_time"] += count
        self.save()

    def remaining_today(self) -> int:
        """Remaining quota under today's daily budget."""
        return max(0, config.DAILY_BUDGET - self.state["unliked_today"])

    def can_proceed_today(self) -> bool:
        """Check if today's daily budget has been reached."""
        return self.state["unliked_today"] < config.DAILY_BUDGET

    def get_progress_summary(self) -> Dict[str, Any]:
        """Return high-level summary metrics."""
        baseline = self.state.get("baseline_total", config.ESTIMATED_TOTAL_LIKES)
        all_time = self.state.get("total_unliked_all_time", 0)
        remaining_est = max(0, baseline - all_time)
        return {
            "unliked_today": self.state["unliked_today"],
            "daily_budget": config.DAILY_BUDGET,
            "total_unliked_all_time": all_time,
            "baseline_total": baseline,
            "remaining_est": remaining_est,
        }


def setup_logging() -> logging.Logger:
    """Configure console output and daily rotating log file."""
    today = datetime.date.today().isoformat()
    log_file = config.LOGS_DIR / f"run_{today}.log"

    logger = logging.getLogger("insta_unlike")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on re-entry
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Terminal handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            "[%(asctime)s] %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
