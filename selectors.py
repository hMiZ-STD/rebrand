"""
Centralized UI locators and selectors for Instagram's 'Your Activity' Likes page.
Matches live DOM structure (Meta wbloks component hierarchy).
"""
import re

# Navigation & Select Mode
SELECT_TRIGGER = 'span:text-is("Select"), div[role="button"]:has-text("Select"), button:has-text("Select")'
CANCEL_TRIGGER = 'span:text-is("Cancel"), div[role="button"]:has-text("Cancel"), button:has-text("Cancel")'

# Post Thumbnails in Activity Grid
# Each post is an image with clickable parent div
POST_TILE_IMAGES = 'main [style*="padding-bottom"] img, main img[style*="object-fit"], div[style*="cursor: pointer"] img'

# Selection Bar & Counter
SELECTED_COUNT_PATTERN = re.compile(r"(\d+)\s+selected", re.IGNORECASE)
UNLIKE_TRIGGER = 'div[role="button"][aria-label="Unlike"][style*="pointer-events: auto"], div[role="button"][aria-label="Unlike"]'

# Confirmation Modal Dialog (Strictly target the VISIBLE dialog containing the word 'Unlike')
DIALOG_SELECTOR = 'div[role="dialog"]:has-text("Unlike")'
DIALOG_CONFIRM_UNLIKE = 'div[role="dialog"]:has-text("Unlike") button:has-text("Unlike"), div[role="dialog"]:has-text("Unlike") [role="button"]:has-text("Unlike"), div[role="dialog"]:has-text("Unlike") span:text-is("Unlike")'
DIALOG_CANCEL = 'div[role="dialog"] button:has-text("Cancel"), div[role="dialog"] [role="button"]:has-text("Cancel"), div[role="dialog"] span:text-is("Cancel")'

# Spinners & Loading Placeholders
SPINNER_SELECTOR = 'svg[aria-label="Loading..."], [role="progressbar"]'

# Notification & Cookie Popups ("Not Now", "Allow essential", etc.)
DISMISS_POPUP_TEXTS = [
    re.compile(r"^Not Now$", re.IGNORECASE),
    re.compile(r"^Cancel$", re.IGNORECASE),
    re.compile(r"^Decline optional cookies$", re.IGNORECASE),
    re.compile(r"^Only allow essential cookies$", re.IGNORECASE),
    re.compile(r"^Allow all cookies$", re.IGNORECASE),
    re.compile(r"^Close$", re.IGNORECASE),
]

# Account Restriction & Block Indicators
BLOCK_SIGNATURES = [
    "Action Blocked",
    "Try Again Later",
    "We limit how often",
    "We restrict certain activity",
    "Something went wrong",
    "Help us confirm you own this account",
    "Please wait a few minutes before you try again",
    "Your account has been temporarily blocked",
]

# Sensitive URL paths indicating session loss or challenges
CHALLENGE_URL_PARTS = [
    "/challenge/",
    "/two_factor/",
    "/accounts/login/",
    "/integrity/checkpoint/",
]

# Empty State Signatures (zero likes remaining)
EMPTY_STATE_SIGNATURES = [
    "You haven't liked any posts",
    "No likes yet",
    "No results found",
    "Nothing to see here",
]
