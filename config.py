"""
Configuration for the Sonos Stock Checker.

All settings can be controlled via environment variables.
For GitHub Actions, set these as repository secrets.
For local use, set them in your shell or a .env file.
"""

import os
import json


# ─────────────────────────────────────────────────────────
# Product URLs to monitor
# ─────────────────────────────────────────────────────────
# Set SONOS_PRODUCT_URLS as a JSON array of URLs, e.g.:
#   ["https://www.sonos.com/de-de/shop/one-sl-b-stock", "https://www.sonos.com/de-de/shop/arc-b-stock"]
#
# Or leave empty to use the default list below.

_default_urls = [
    "https://www.sonos.com/de-de/shop/one-sl-b-stock",
]

PRODUCT_URLS: list[str] = json.loads(
    os.environ.get("SONOS_PRODUCT_URLS", "[]")
) or _default_urls


# ─────────────────────────────────────────────────────────
# Email settings  (Gmail SMTP)
# ─────────────────────────────────────────────────────────
# GMAIL_ADDRESS  – your full Gmail address (sender + default recipient)
# GMAIL_APP_PASSWORD – a Gmail App Password (NOT your regular password)
# NOTIFY_EMAIL   – (optional) override recipient address

GMAIL_ADDRESS: str = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD: str = os.environ.get("GMAIL_APP_PASSWORD", "")
NOTIFY_EMAIL: str = os.environ.get("NOTIFY_EMAIL", "") or GMAIL_ADDRESS

SMTP_HOST: str = "smtp.gmail.com"
SMTP_PORT: int = 587


# ─────────────────────────────────────────────────────────
# Request settings
# ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT: int = 30  # seconds

# Realistic browser User-Agent to avoid being blocked
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# ─────────────────────────────────────────────────────────
# Local-run settings (ignored by GitHub Actions)
# ─────────────────────────────────────────────────────────
CHECK_INTERVAL_MINUTES: int = int(os.environ.get("CHECK_INTERVAL_MINUTES", "15"))
