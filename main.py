"""
main.py
───────
Tech Trend Monitor – Main Pipeline

Orchestrates all steps:
  1. Run all scrapers
  2. Store raw data in SQLite
  3. Detect trending keywords
  4. Generate NLP summaries
  5. Save weekly summary to DB
  6. Send email report (if configured)

Usage
-----
  python main.py                  # run once
  python main.py --no-email       # skip email even if EMAIL_ENABLED=true
  python main.py --dry-run        # scrape + print, no DB writes
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from loguru import logger

# ── Logging to file ───────────────────────────────────────────────────────────
from config import LOG_DIR
log_file = LOG_DIR / "pipeline.log"
logger.add(
    str(log_file),
    rotation="1 week",
    retention="4 weeks",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    enqueue=True,
)


def run_pipeline(send_email: bool = True) -> dict:
    """
    Execute the full Tech Trend Monitor pipeline.

    Parameters
    ----------
    send_email : bool  – if False, skip the email step regardless of config

    Returns
    -------
    dict with pipeline statistics
    """
    start_time = datetime.datetime.utcnow()
    logger.info("=" * 60)
    logger.info(f"Pipeline started at {start_time:%Y-%m-%d %H:%M:%S} UTC")
    logger.info("=" * 60)

    stats = {
        "start_time"  : start_time.isoformat(),
        "repos_count" : 0,
        "blogs_count" : 0,
        "ai_news_count": 0,
        "email_sent"  : False,
        "errors"      : [],
    }

    # ── Step 1: Initialise database ───────────────────────────────────────────
    logger.info("Step 1 ▸ Initialising database …")
    try:
        from database.db_manager import (
            init_db,
            insert_github_repos,
            insert_blog_posts,
            insert_ai_news,
            upsert_weekly_summary,
            fetch_github_repos,
            fetch_blog_posts,
            fetch_ai_news,
        )
        init_db()
    except Exception as exc:
        logger.exception(f"DB init failed: {exc}")
        stats["errors"].append(f"DB init: {exc}")
        return stats

    # ── Step 2: Scrape GitHub Trending ────────────────────────────────────────
    logger.info("Step 2 ▸ Scraping GitHub trending …")
    try:
        from scraper.github_scraper import scrape_all_languages
        repos = scrape_all_languages()
        insert_github_repos(repos)
        stats["repos_count"] = len(repos)
        logger.success(f"  ✔ {len(repos)} repos scraped & stored")
    except Exception as exc:
        logger.exception(f"GitHub scraper failed: {exc}")
        stats["errors"].append(f"GitHub scraper: {exc}")
        repos = []

    # ── Step 3: Scrape Tech Blogs ─────────────────────────────────────────────
    logger.info("Step 3 ▸ Scraping tech blogs …")
    try:
        from scraper.blog_scraper import scrape_all_blogs
        blogs = scrape_all_blogs()
        insert_blog_posts(blogs)
        stats["blogs_count"] = len(blogs)
        logger.success(f"  ✔ {len(blogs)} blog posts scraped & stored")
    except Exception as exc:
        logger.exception(f"Blog scraper failed: {exc}")
        stats["errors"].append(f"Blog scraper: {exc}")
        blogs = []

    # ── Step 4: Scrape AI News ────────────────────────────────────────────────
    logger.info("Step 4 ▸ Scraping AI news …")
    try:
        from scraper.ai_news_scraper import scrape_all_ai_news
        ai_news = scrape_all_ai_news()
        insert_ai_news(ai_news)
        stats["ai_news_count"] = len(ai_news)
        logger.success(f"  ✔ {len(ai_news)} AI news articles scraped & stored")
    except Exception as exc:
        logger.exception(f"AI news scraper failed: {exc}")
        stats["errors"].append(f"AI news scraper: {exc}")
        ai_news = []

    # ── Step 5: Detect Trends ─────────────────────────────────────────────────
    logger.info("Step 5 ▸ Detecting trends …")
    try:
        from processing.trend_detector import detect_trends

        # Re-fetch from DB to ensure we're working with the saved, cleaned data
        repos_db   = fetch_github_repos(limit=200)  or repos
        blogs_db   = fetch_blog_posts  (limit=500)  or blogs
        ai_news_db = fetch_ai_news     (limit=500)  or ai_news

        trends = detect_trends(repos_db, blogs_db, ai_news_db)
        logger.success(f"  ✔ Top keywords: {[k['keyword'] for k in trends['overall'][:5]]}")
    except Exception as exc:
        logger.exception(f"Trend detection failed: {exc}")
        stats["errors"].append(f"Trend detection: {exc}")
        trends = {"overall": [], "top_languages": [], "keywords_json": "[]"}
        repos_db = repos; blogs_db = blogs; ai_news_db = ai_news

    # ── Step 6: Generate Summaries ────────────────────────────────────────────
    logger.info("Step 6 ▸ Generating NLP summaries …")
    try:
        from processing.summarizer import (
            summarize_github_trends,
            summarize_blog_posts,
            summarize_ai_news,
        )
        github_summary  = summarize_github_trends(repos_db)
        blog_summary    = summarize_blog_posts(blogs_db)
        ai_news_summary = summarize_ai_news(ai_news_db)
        logger.success("  ✔ Summaries generated")
    except Exception as exc:
        logger.exception(f"Summarisation failed: {exc}")
        stats["errors"].append(f"Summarisation: {exc}")
        github_summary  = "Summary unavailable."
        blog_summary    = "Summary unavailable."
        ai_news_summary = "Summary unavailable."

    # ── Step 7: Save Weekly Summary ───────────────────────────────────────────
    logger.info("Step 7 ▸ Saving weekly summary …")
    try:
        upsert_weekly_summary(
            top_keywords    = trends.get("keywords_json", "[]"),
            github_summary  = github_summary,
            blog_summary    = blog_summary,
            ai_news_summary = ai_news_summary,
        )
        logger.success("  ✔ Weekly summary saved to DB")
    except Exception as exc:
        logger.exception(f"Summary save failed: {exc}")
        stats["errors"].append(f"Summary save: {exc}")

    # ── Step 8: Send Email ────────────────────────────────────────────────────
    if send_email:
        logger.info("Step 8 ▸ Sending email report …")
        try:
            from notifier.email_sender import send_weekly_report
            from database.db_manager   import fetch_weekly_summary

            summary_row = fetch_weekly_summary()
            if summary_row:
                email_sent = send_weekly_report(
                    summary  = summary_row,
                    trends   = trends,
                    repos    = repos_db,
                )
                stats["email_sent"] = email_sent
                if email_sent:
                    logger.success("  ✔ Email report sent")
                else:
                    logger.info("  ℹ Email not sent (disabled or misconfigured)")
        except Exception as exc:
            logger.exception(f"Email step failed: {exc}")
            stats["errors"].append(f"Email: {exc}")
    else:
        logger.info("Step 8 ▸ Email step skipped (--no-email)")

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
    stats["elapsed_seconds"] = round(elapsed, 1)

    logger.info("=" * 60)
    logger.success(
        f"Pipeline finished in {elapsed:.1f}s | "
        f"Repos: {stats['repos_count']} | "
        f"Blogs: {stats['blogs_count']} | "
        f"AI News: {stats['ai_news_count']} | "
        f"Errors: {len(stats['errors'])}"
    )
    if stats["errors"]:
        for err in stats["errors"]:
            logger.warning(f"  ⚠ {err}")
    logger.info("=" * 60)

    return stats


# ── CLI entry point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Tech Trend Monitor – run the full pipeline"
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip the email step (override EMAIL_ENABLED)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run scrapers and print results, skip DB writes + email",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode – no DB writes or emails")
        from scraper.github_scraper import scrape_all_languages
        repos = scrape_all_languages()
        logger.info(f"Scraped {len(repos)} repos")
        print(json.dumps(repos[:3], indent=2))
        sys.exit(0)

    result = run_pipeline(send_email=not args.no_email)

    # Exit with non-zero code if there were errors
    sys.exit(1 if result.get("errors") else 0)
