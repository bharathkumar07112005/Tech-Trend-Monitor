"""
config.py – Central configuration for Tech Trend Monitor.
All settings are loaded from environment variables (or .env file).
Copy .env.example → .env and fill in your values.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root if present
load_dotenv(Path(__file__).parent / ".env")

# ─── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "data" / "tech_trends.db"
LOG_DIR  = BASE_DIR / "logs"

# Create directories if they don't exist
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ─── Scraper Settings ─────────────────────────────────────────────────────────
REQUEST_TIMEOUT   = 15          # seconds
REQUEST_HEADERS   = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
MAX_RETRIES       = 3
RETRY_WAIT_SECS   = 5

# GitHub trending page URL
GITHUB_TRENDING_URL = "https://github.com/trending"
GITHUB_LANGUAGES    = ["python", "javascript", "rust", "go", "typescript", ""]  # "" = all

# Tech blog RSS feeds – add / remove freely
BLOG_RSS_FEEDS = {
    "Hacker News"      : "https://news.ycombinator.com/rss",
    "TechCrunch"       : "https://techcrunch.com/feed/",
    "The Verge Tech"   : "https://www.theverge.com/rss/index.xml",
    "Ars Technica"     : "http://feeds.arstechnica.com/arstechnica/technology-lab",
    "MIT Tech Review"  : "https://www.technologyreview.com/feed/",
    "Dev.to"           : "https://dev.to/feed",
}

# AI-specific news RSS feeds
AI_NEWS_FEEDS = {
    "OpenAI Blog"      : "https://openai.com/blog/rss.xml",
    "Google AI Blog"   : "https://blog.google/technology/ai/rss/",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Papers With Code" : "https://paperswithcode.com/latest.xml",
    "AI News"          : "https://artificialintelligence-news.com/feed/",
}

MAX_ARTICLES_PER_FEED = 20      # cap per source per run

# ─── NLP / Trend Detection ────────────────────────────────────────────────────
TOP_N_KEYWORDS      = 30        # keywords to surface per run
TOP_N_REPOS         = 20        # repos to show in dashboard
MIN_WORD_LENGTH     = 3
EXTRACTIVE_SENTENCES = 4        # sentences in extractive summary

# Use advanced transformer summarization?  Requires transformers + torch.
USE_TRANSFORMER_SUMMARY = os.getenv("USE_TRANSFORMER_SUMMARY", "false").lower() == "true"
TRANSFORMER_MODEL       = "sshleifer/distilbart-cnn-12-6"  # small, fast

# ─── Email (SMTP) ─────────────────────────────────────────────────────────────
EMAIL_ENABLED    = os.getenv("EMAIL_ENABLED", "false").lower() == "true"
SMTP_HOST        = os.getenv("SMTP_HOST",   "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER        = os.getenv("SMTP_USER",   "")           # your Gmail address
SMTP_PASSWORD    = os.getenv("SMTP_PASSWORD", "")         # app password (not Gmail password)
EMAIL_FROM       = os.getenv("EMAIL_FROM",  SMTP_USER)
EMAIL_TO         = os.getenv("EMAIL_TO",    "").split(",")  # comma-separated list

# ─── Scheduler ────────────────────────────────────────────────────────────────
SCHEDULE_DAY     = "monday"     # day of week for weekly run
SCHEDULE_TIME    = "08:00"      # 24-hour local time

# ─── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_TITLE  = "🚀 Tech Trend Monitor"
DASHBOARD_PORT   = int(os.getenv("DASHBOARD_PORT", "8501"))
