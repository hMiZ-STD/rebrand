import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
USER_DATA_DIR = BASE_DIR / "ig_profile"
LOGS_DIR = BASE_DIR / "logs"
SCREENSHOTS_DIR = LOGS_DIR / "screenshots"
STATE_FILE = LOGS_DIR / "state.json"

# Ensure runtime directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Instagram URLs
BASE_URL = "https://www.instagram.com/your_activity/interactions/likes/"
LOGIN_URL = "https://www.instagram.com/accounts/login/"

# Budget & Safety Thresholds
# Conservative default: 250 unlikes per day
DAILY_BUDGET = 250
ESTIMATED_TOTAL_LIKES = 3000  # Baseline total (from export or rough estimate)

# Delays & Human-Like Pacing (in seconds)
# Jittered click delay between selecting individual posts
CLICK_DELAY_MIN = 0.5
CLICK_DELAY_MAX = 1.4

# Cooldown between batches
BATCH_DELAY_MIN = 12.0
BATCH_DELAY_MAX = 25.0

# Extended "coffee break" to break up automation monotony
COFFEE_BREAK_EVERY_N_BATCHES_MIN = 4
COFFEE_BREAK_EVERY_N_BATCHES_MAX = 6
COFFEE_BREAK_DURATION_MIN = 60.0   # 1 minute
COFFEE_BREAK_DURATION_MAX = 180.0  # 3 minutes

# Batch & Grid Logic
# Maximum posts to select in a single batch (Instagram web UI typically caps at ~50-100)
MAX_BATCH_SIZE = 50
MAX_STUCK_BATCHES = 3  # Stop if N consecutive batches result in 0 unlikes removed
PAGE_TIMEOUT_MS = 45000
ACTION_TIMEOUT_MS = 15000

# Browser Settings
HEADLESS = False  # Keep headed for maximum safety & visibility
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 850
