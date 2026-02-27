import os
from dotenv import load_dotenv

load_dotenv()

def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value.strip()

# Bot
TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")

# Email / SMTP
SMTP_EMAIL    = _require("SMTP_EMAIL")
SMTP_PASSWORD = _require("SMTP_PASSWORD")

# Optional AI keys (bot can also use user-provided keys from DB)
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Database
MONGODB_URI = _require("MONGODB_URI")

# ── Personal profile (edit here to personalise the outreach emails) ───────────
PROFILE = {
    "name":       "Your Name",
    "phone":      "+1234567890",
    "linkedin":   "https://www.linkedin.com/in/yourprofile/",
    "github":     "https://github.com/yourusername",
    "university": "Your University",
    "year":       "final year undergraduate",
}

SIGNATURE = (
    f"\\n\\nBest regards,\\n"
    f"{PROFILE['name']}\\n"
    f"Contact: {PROFILE['phone']}\\n"
    f"LinkedIn: {PROFILE['linkedin']}\\n"
    f"GitHub: {PROFILE['github']}"
)
