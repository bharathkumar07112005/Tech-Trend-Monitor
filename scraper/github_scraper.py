"""
scraper/github_scraper.py
─────────────────────────
Scrapes GitHub Trending (https://github.com/trending) for each configured
language and returns a list of structured repository dicts.

No GitHub API token required – uses plain HTTP scraping.
"""

import datetime
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from config import (
    GITHUB_TRENDING_URL,
    GITHUB_LANGUAGES,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    MAX_RETRIES,
    RETRY_WAIT_SECS,
    TOP_N_REPOS,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _clean(text: Optional[str]) -> str:
    """Strip whitespace / newlines from scraped text."""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", text).strip()


@retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_fixed(RETRY_WAIT_SECS))
def _fetch_html(url: str) -> str:
    """Fetch URL with retries.  Raises on non-2xx status."""
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


# ── Main scraper ─────────────────────────────────────────────────────────────

def scrape_language(language: str = "") -> list[dict]:
    """
    Scrape GitHub trending for one language.

    Parameters
    ----------
    language : str
        Lower-case GitHub language slug (e.g. "python") or "" for all languages.

    Returns
    -------
    list[dict]  – each dict has keys:
        rank, name, full_name, url, description, language,
        stars_today, total_stars, forks, scraped_at
    """
    url = f"{GITHUB_TRENDING_URL}/{language}" if language else GITHUB_TRENDING_URL
    scraped_at = datetime.datetime.utcnow().isoformat()

    logger.info(f"Scraping GitHub trending | language='{language or 'all'}' | url={url}")

    try:
        html = _fetch_html(url)
    except Exception as exc:
        logger.error(f"Failed to fetch {url}: {exc}")
        return []

    soup = BeautifulSoup(html, "lxml")
    repo_items = soup.select("article.Box-row")

    repos = []
    for rank, item in enumerate(repo_items[:TOP_N_REPOS], start=1):
        try:
            # ── Name & URL ──────────────────────────────────────────────────
            h2 = item.select_one("h2 a")
            full_name = _clean(h2.get_text()) if h2 else ""
            full_name = full_name.replace(" ", "")          # "owner / repo" → "owner/repo"
            repo_url  = f"https://github.com{h2['href']}" if h2 else ""
            parts     = full_name.split("/")
            name      = parts[-1] if parts else full_name

            # ── Description ─────────────────────────────────────────────────
            desc_tag  = item.select_one("p")
            desc      = _clean(desc_tag.get_text()) if desc_tag else ""

            # ── Language ────────────────────────────────────────────────────
            lang_tag  = item.select_one("[itemprop='programmingLanguage']")
            lang      = _clean(lang_tag.get_text()) if lang_tag else (language or "Unknown")

            # ── Stars & forks ───────────────────────────────────────────────
            stat_spans = item.select("a.Link--muted")
            total_stars = _parse_number(_clean(stat_spans[0].get_text())) if len(stat_spans) > 0 else 0
            forks       = _parse_number(_clean(stat_spans[1].get_text())) if len(stat_spans) > 1 else 0

            # Stars today lives in a separate <span>
            today_span  = item.select_one("span.d-inline-block.float-sm-right")
            stars_today = _parse_number(_clean(today_span.get_text())) if today_span else 0

            repos.append({
                "rank"        : rank,
                "name"        : name,
                "full_name"   : full_name,
                "url"         : repo_url,
                "description" : desc,
                "language"    : lang,
                "stars_today" : stars_today,
                "total_stars" : total_stars,
                "forks"       : forks,
                "scraped_at"  : scraped_at,
            })

        except Exception as exc:
            logger.warning(f"Skipping repo at rank {rank}: {exc}")
            continue

    logger.success(f"Scraped {len(repos)} repos for language='{language or 'all'}'")
    return repos


def _parse_number(text: str) -> int:
    """Convert '1,234' or '5.6k' style strings to int."""
    text = text.replace(",", "").strip()
    if not text:
        return 0
    try:
        if text.lower().endswith("k"):
            return int(float(text[:-1]) * 1_000)
        return int(text.split()[0])
    except (ValueError, IndexError):
        return 0


def scrape_all_languages() -> list[dict]:
    """
    Scrape GitHub trending for every language in GITHUB_LANGUAGES.
    Deduplicates by full_name, keeping the entry with most stars_today.

    Returns a flat list of repo dicts.
    """
    seen: dict[str, dict] = {}

    for lang in GITHUB_LANGUAGES:
        for repo in scrape_language(lang):
            key = repo["full_name"]
            if key not in seen or repo["stars_today"] > seen[key]["stars_today"]:
                seen[key] = repo

    results = sorted(seen.values(), key=lambda r: r["stars_today"], reverse=True)
    logger.info(f"Total unique trending repos scraped: {len(results)}")
    return results


# ── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    repos = scrape_all_languages()
    print(json.dumps(repos[:3], indent=2))
