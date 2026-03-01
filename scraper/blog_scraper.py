"""
scraper/blog_scraper.py
───────────────────────
Fetches recent posts from tech blog RSS / Atom feeds defined in config.py.
Uses feedparser so it handles RSS 2.0, Atom 1.0 transparently.
"""

import datetime
import re
from html import unescape

import feedparser
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config import (
    BLOG_RSS_FEEDS,
    MAX_ARTICLES_PER_FEED,
    MAX_RETRIES,
    RETRY_WAIT_SECS,
    REQUEST_TIMEOUT,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_html(raw: str) -> str:
    """Remove HTML tags and decode entities."""
    clean = re.sub(r"<[^>]+>", " ", raw or "")
    clean = unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def _parse_date(entry) -> str:
    """Return ISO-8601 date string from a feedparser entry."""
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            try:
                dt = datetime.datetime(*parsed[:6])
                return dt.isoformat()
            except Exception:
                pass
    return datetime.datetime.utcnow().isoformat()


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_WAIT_SECS))
def _fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch + parse RSS/Atom feed with a timeout hack via requests."""
    import requests

    # feedparser doesn't support timeout natively, so fetch raw then parse
    from config import REQUEST_HEADERS
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return feedparser.parse(resp.text)


# ── Main scraper ─────────────────────────────────────────────────────────────

def scrape_feed(source_name: str, feed_url: str) -> list[dict]:
    """
    Parse one RSS / Atom feed and return structured article dicts.

    Returns
    -------
    list[dict] – keys: title, url, summary, source, published_at, scraped_at
    """
    scraped_at = datetime.datetime.utcnow().isoformat()
    logger.info(f"Scraping blog feed: {source_name}")

    try:
        feed = _fetch_feed(feed_url)
    except Exception as exc:
        logger.error(f"Failed to fetch feed '{source_name}': {exc}")
        return []

    articles = []
    for entry in feed.entries[:MAX_ARTICLES_PER_FEED]:
        try:
            title   = _strip_html(getattr(entry, "title", ""))
            url     = getattr(entry, "link",  "")

            # Try multiple fields for body text
            raw_summary = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
                or getattr(entry, "content", [{}])[0].get("value", "") if hasattr(entry, "content") else ""
            )
            summary = _strip_html(raw_summary)[:1000]   # cap at 1 000 chars

            articles.append({
                "title"        : title,
                "url"          : url,
                "summary"      : summary,
                "source"       : source_name,
                "published_at" : _parse_date(entry),
                "scraped_at"   : scraped_at,
            })
        except Exception as exc:
            logger.warning(f"Skipping entry in '{source_name}': {exc}")
            continue

    logger.success(f"Fetched {len(articles)} articles from '{source_name}'")
    return articles


def scrape_all_blogs() -> list[dict]:
    """
    Scrape every feed in BLOG_RSS_FEEDS.

    Returns a combined, date-sorted list of article dicts.
    """
    all_articles: list[dict] = []

    for name, url in BLOG_RSS_FEEDS.items():
        all_articles.extend(scrape_feed(name, url))

    # Sort newest-first
    all_articles.sort(key=lambda a: a["published_at"], reverse=True)
    logger.info(f"Total blog articles scraped: {len(all_articles)}")
    return all_articles


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    articles = scrape_all_blogs()
    print(json.dumps(articles[:2], indent=2))
