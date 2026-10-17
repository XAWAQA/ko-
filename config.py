"""
Configuration module for Telegram Bot and Facebook Operations.
Loads settings from environment variables with safe defaults and validation.
"""

import os
import sys

# Attempt to load local .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔐 Secrets & Credentials (Loaded from Env)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 👑 Ownership & Access Control Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OWNER_ID = int(os.environ.get("OWNER_ID", "1167798421"))
ACCESS_DB_PATH = os.environ.get(
    "ACCESS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "access_control.db"),
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⚙️ Hardware & Concurrency Defaults
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPU_CORES = os.cpu_count() or 4
MAX_RAM_MB = int(os.environ.get("MAX_RAM_MB", "8192"))
FF_CHECKER_CONCURRENCY = int(os.environ.get("FF_CHECKER_CONCURRENCY", "5"))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📡 Network & Request Configuration
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GRAPH_API_BASE_URL = os.environ.get("GRAPH_API_BASE_URL", "https://graph.facebook.com").rstrip("/")
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "12.0"))
RETRY_ATTEMPTS = int(os.environ.get("RETRY_ATTEMPTS", "3"))
RETRY_BACKOFF = [0.3, 0.7, 1.5]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🏎️ Supported Operational Speeds
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SPEED_OPTIONS = [1, 5, 10, 50, 100, 200, 350, 500]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ⏱️ UI Update Rates
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROGRESS_UPDATE_INTERVAL = float(os.environ.get("PROGRESS_UPDATE_INTERVAL", "1.5"))


def validate_config() -> None:
    """
    Validates required configuration at application startup.
    Exits gracefully with an informative message if required secrets are absent.
    """
    if not TELEGRAM_BOT_TOKEN:
        print("=" * 60, file=sys.stderr)
        print("❌ CONFIGURATION ERROR: TELEGRAM_BOT_TOKEN is not configured.", file=sys.stderr)
        print("Please set the TELEGRAM_BOT_TOKEN environment variable.", file=sys.stderr)
        print("Example (Windows cmd):   set TELEGRAM_BOT_TOKEN=your_token_here", file=sys.stderr)
        print("Example (PowerShell):    $env:TELEGRAM_BOT_TOKEN=\"your_token_here\"", file=sys.stderr)
        print("Example (Linux/macOS):   export TELEGRAM_BOT_TOKEN=\"your_token_here\"", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        sys.exit(1)
