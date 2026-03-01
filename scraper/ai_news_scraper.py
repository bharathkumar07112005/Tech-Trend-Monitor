"""
scraper/ai_news_scraper.py
──────────────────────────
Dedicated scraper for AI-focused RSS feeds defined in config.AI_NEWS_FEEDS.
Identical in structure to blog_scraper but kept separate so the database
can store AI news in its own table and trend detection can weight it
differently.
"""

import datetime
import re
from html import unescape

import feedparser
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config import (
    AI_NEWS_FEEDS,
    MAX_ARTICLES_PER_FEED,
    MAX_RETRIES,
    RETRY_WAIT_SECS,
    REQUEST_TIMEOUT,
    REQUEST_HEADERS,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _strip_html(raw: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw or "")
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _parse_date(entry) -> str:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                return datetime.datetime(*parsed[:6]).isoformat()
            except Exception:
                pass
    return datetime.datetime.utcnow().isoformat()


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_WAIT_SECS))
def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.text)


# ── Per-feed scraper ──────────────────────────────────────────────────────────

def scrape_ai_feed(source_name: str, feed_url: str) -> list[dict]:
    """
    Fetch one AI-news feed.

    Returns
    -------
    list[dict] – keys: title, url, summary, source, published_at, scraped_at
    """
    scraped_at = datetime.datetime.utcnow().isoformat()
    logger.info(f"Scraping AI news feed: {source_name}")

    try:
        feed = _fetch_feed(feed_url)
    except Exception as exc:
        logger.error(f"Failed to fetch AI feed '{source_name}': {exc}")
        return []

    items = []
    for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
        try:
            title = _strip_html(getattr(entry, "title", ""))
            url   = getattr(entry, "link", "")

            raw = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
            )
            if not raw and hasattr(entry, "content"):
                raw = entry.content[0].get("value", "") if entry.content else ""

            summary = _strip_html(raw)[:1000]

            # Heuristic: tag entries that look like model/product releases
            is_release = any(
                kw in title.lower()
                for kw in ("release", "launch", "announce", "unveil", "introduce", "v2", "v3", "gpt", "llm")
            )

            items.append({
                "title"        : title,
                "url"          : url,
                "summary"      : summary,
                "source"       : source_name,
                "is_release"   : int(is_release),   # store as 0/1 in SQLite
                "published_at" : _parse_date(entry),
                "scraped_at"   : scraped_at,
            })
        except Exception as exc:
            logger.warning(f"Skipping AI entry in '{source_name}': {exc}")
            continue

    logger.success(f"Fetched {len(items)} AI articles from '{source_name}'")
    return items


# ── Aggregate scraper ─────────────────────────────────────────────────────────

def scrape_all_ai_news() -> list[dict]:
    """
    Scrape every feed in AI_NEWS_FEEDS.
    Returns a combined list sorted newest-first.
    """
    all_items: list[dict] = []

    for name, url in AI_NEWS_FEEDS.items():
        all_items.extend(scrape_ai_feed(name, url))

    all_items.sort(key=lambda a: a["published_at"], reverse=True)
    logger.info(f"Total AI news articles scraped: {len(all_items)}")
    return all_items


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    news = scrape_all_ai_news()
    print(json.dumps(news[:2], indent=2))
