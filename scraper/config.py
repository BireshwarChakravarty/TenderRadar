"""
TenderRadar — Central configuration
Reads from environment variables (set as GitHub Secrets in production,
or in a local .env file for development).
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if running locally
load_dotenv(Path(__file__).parent.parent / ".env")

# ── Core ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
COMPANY_PROFILE     = os.getenv(
    "COMPANY_PROFILE",
    "Communications and PR agency specialising in integrated communications strategy, "
    "social media management, digital outreach, creative content development, media monitoring, "
    "event publicity, and communication support services. We execute mandates involving strategy, "
    "content, creative, digital engagement, reputation management, analytics, and campaign "
    "execution for government, public-sector, institutional, and corporate clients in India."
)
MIN_RELEVANCE_SCORE = float(os.getenv("MIN_RELEVANCE_SCORE", "6.0"))
REQUEST_DELAY       = float(os.getenv("REQUEST_DELAY_SECONDS", "3"))
USER_AGENT          = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# ── Portals enabled ───────────────────────────────────────────────────
SCRAPE_GEM   = os.getenv("SCRAPE_GEM",   "true").lower() == "true"
SCRAPE_CPPP  = os.getenv("SCRAPE_CPPP",  "true").lower() == "true"
SCRAPE_BHEL  = os.getenv("SCRAPE_BHEL",  "true").lower() == "true"
SCRAPE_ONGC  = os.getenv("SCRAPE_ONGC",  "true").lower() == "true"
SCRAPE_NTPC  = os.getenv("SCRAPE_NTPC",  "true").lower() == "true"
SCRAPE_STATE = os.getenv("SCRAPE_STATE", "true").lower() == "true"

# Allow manual portal override from workflow_dispatch
_override = os.getenv("PORTALS_OVERRIDE", "").strip()
if _override:
    _enabled = {p.strip().lower() for p in _override.split(",")}
    SCRAPE_GEM   = "gem"   in _enabled
    SCRAPE_CPPP  = "cppp"  in _enabled
    SCRAPE_BHEL  = "bhel"  in _enabled
    SCRAPE_ONGC  = "ongc"  in _enabled
    SCRAPE_NTPC  = "ntpc"  in _enabled
    SCRAPE_STATE = "state" in _enabled

# ── Email ─────────────────────────────────────────────────────────────
EMAIL_ENABLED  = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
SMTP_HOST      = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT      = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER      = os.getenv("SMTP_USER", "")
SMTP_PASS      = os.getenv("SMTP_PASS", "")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "")

# ── Telegram ──────────────────────────────────────────────────────────
TELEGRAM_ENABLED   = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── File paths ────────────────────────────────────────────────────────
ROOT_DIR       = Path(__file__).parent.parent
DATA_DIR       = ROOT_DIR / "data"
TENDERS_FILE   = DATA_DIR / "tenders.json"
ALERT_LOG_FILE = DATA_DIR / "alert_log.json"
DATA_DIR.mkdir(exist_ok=True)
