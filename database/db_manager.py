"""
database/db_manager.py
──────────────────────
SQLite wrapper.  Creates tables on first run; provides insert / fetch helpers
for every data type used by the pipeline.

Tables
------
  github_trends   – trending GitHub repositories
  blog_posts      – tech-blog articles
  ai_news         – AI-specific news articles
  weekly_summary  – generated summaries stored per run
"""

import sqlite3
import datetime
from contextlib import contextmanager
from typing import Generator

from loguru import logger

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import DB_PATH


# ── Schema ────────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS github_trends (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    rank         INTEGER,
    name         TEXT,
    full_name    TEXT,
    url          TEXT,
    description  TEXT,
    language     TEXT,
    stars_today  INTEGER,
    total_stars  INTEGER,
    forks        INTEGER,
    scraped_at   TEXT,
    week_label   TEXT                         -- e.g. "2024-W12"
);

CREATE TABLE IF NOT EXISTS blog_posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    url          TEXT UNIQUE,
    summary      TEXT,
    source       TEXT,
    published_at TEXT,
    scraped_at   TEXT,
    week_label   TEXT
);

CREATE TABLE IF NOT EXISTS ai_news (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT,
    url          TEXT UNIQUE,
    summary      TEXT,
    source       TEXT,
    is_release   INTEGER DEFAULT 0,
    published_at TEXT,
    scraped_at   TEXT,
    week_label   TEXT
);

CREATE TABLE IF NOT EXISTS weekly_summary (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    week_label        TEXT UNIQUE,
    top_keywords      TEXT,   -- JSON array string
    github_summary    TEXT,
    blog_summary      TEXT,
    ai_news_summary   TEXT,
    created_at        TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_github_week   ON github_trends (week_label);
CREATE INDEX IF NOT EXISTS idx_blog_week     ON blog_posts    (week_label);
CREATE INDEX IF NOT EXISTS idx_ainews_week   ON ai_news       (week_label);
CREATE INDEX IF NOT EXISTS idx_summary_week  ON weekly_summary(week_label);
"""


# ── Connection context ────────────────────────────────────────────────────────

@contextmanager
def _get_conn() -> Generator[sqlite3.Connection, None, None]:
    """Yield an auto-committing SQLite connection; roll back on error."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row          # column-name access
    conn.execute("PRAGMA journal_mode=WAL") # safe concurrent reads
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables + indexes if they don't exist yet."""
    with _get_conn() as conn:
        conn.executescript(_SCHEMA)
    logger.info(f"Database initialised at {DB_PATH}")


# ── Utility ───────────────────────────────────────────────────────────────────

def _week_label(dt: datetime.datetime | None = None) -> str:
    """Return ISO week label like '2024-W12'."""
    dt = dt or datetime.datetime.utcnow()
    return f"{dt.isocalendar().year}-W{dt.isocalendar().week:02d}"


# ── GitHub trends ─────────────────────────────────────────────────────────────

def insert_github_repos(repos: list[dict]) -> int:
    """
    Insert a list of repo dicts.  Existing rows for the same week are replaced
    so re-running the pipeline is idempotent.

    Returns the number of rows inserted.
    """
    if not repos:
        return 0

    week = _week_label()

    # Remove old data for this week so re-runs don't duplicate
    with _get_conn() as conn:
        conn.execute("DELETE FROM github_trends WHERE week_label = ?", (week,))

    sql = """
        INSERT INTO github_trends
            (rank, name, full_name, url, description, language,
             stars_today, total_stars, forks, scraped_at, week_label)
        VALUES
            (:rank, :name, :full_name, :url, :description, :language,
             :stars_today, :total_stars, :forks, :scraped_at, :week_label)
    """
    rows = [{**r, "week_label": week} for r in repos]
    with _get_conn() as conn:
        conn.executemany(sql, rows)

    logger.info(f"Inserted {len(rows)} GitHub repos for {week}")
    return len(rows)


def fetch_github_repos(week_label: str | None = None, limit: int = 100) -> list[dict]:
    """Fetch repos for a given week (defaults to current week)."""
    week = week_label or _week_label()
    sql  = """
        SELECT * FROM github_trends
        WHERE week_label = ?
        ORDER BY stars_today DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (week, limit)).fetchall()
    return [dict(r) for r in rows]


def fetch_recent_github_repos(days: int = 30) -> list[dict]:
    """Fetch repos scraped in the last N days (cross-week)."""
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    sql = """
        SELECT * FROM github_trends
        WHERE scraped_at >= ?
        ORDER BY stars_today DESC
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


# ── Blog posts ────────────────────────────────────────────────────────────────

def insert_blog_posts(posts: list[dict]) -> int:
    """
    Upsert blog posts.  Uses INSERT OR IGNORE on the URL unique constraint
    so duplicate articles from subsequent runs are skipped gracefully.
    """
    if not posts:
        return 0

    week = _week_label()
    sql  = """
        INSERT OR IGNORE INTO blog_posts
            (title, url, summary, source, published_at, scraped_at, week_label)
        VALUES
            (:title, :url, :summary, :source, :published_at, :scraped_at, :week_label)
    """
    rows = [{**p, "week_label": week} for p in posts]
    with _get_conn() as conn:
        conn.executemany(sql, rows)

    logger.info(f"Inserted/skipped {len(rows)} blog posts for {week}")
    return len(rows)


def fetch_blog_posts(week_label: str | None = None, limit: int = 200) -> list[dict]:
    week = week_label or _week_label()
    sql  = """
        SELECT * FROM blog_posts
        WHERE week_label = ?
        ORDER BY published_at DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (week, limit)).fetchall()
    return [dict(r) for r in rows]


def fetch_recent_blog_posts(days: int = 30) -> list[dict]:
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    sql = "SELECT * FROM blog_posts WHERE scraped_at >= ? ORDER BY published_at DESC"
    with _get_conn() as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


# ── AI News ───────────────────────────────────────────────────────────────────

def insert_ai_news(articles: list[dict]) -> int:
    if not articles:
        return 0

    week = _week_label()
    sql  = """
        INSERT OR IGNORE INTO ai_news
            (title, url, summary, source, is_release, published_at, scraped_at, week_label)
        VALUES
            (:title, :url, :summary, :source, :is_release, :published_at, :scraped_at, :week_label)
    """
    rows = [{**a, "week_label": week, "is_release": a.get("is_release", 0)} for a in articles]
    with _get_conn() as conn:
        conn.executemany(sql, rows)

    logger.info(f"Inserted/skipped {len(rows)} AI news articles for {week}")
    return len(rows)


def fetch_ai_news(week_label: str | None = None, limit: int = 200) -> list[dict]:
    week = week_label or _week_label()
    sql  = """
        SELECT * FROM ai_news
        WHERE week_label = ?
        ORDER BY published_at DESC
        LIMIT ?
    """
    with _get_conn() as conn:
        rows = conn.execute(sql, (week, limit)).fetchall()
    return [dict(r) for r in rows]


def fetch_recent_ai_news(days: int = 30) -> list[dict]:
    cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    sql = "SELECT * FROM ai_news WHERE scraped_at >= ? ORDER BY published_at DESC"
    with _get_conn() as conn:
        rows = conn.execute(sql, (cutoff,)).fetchall()
    return [dict(r) for r in rows]


# ── Weekly summary ────────────────────────────────────────────────────────────

def upsert_weekly_summary(
    top_keywords: str,
    github_summary: str,
    blog_summary: str,
    ai_news_summary: str,
    week_label: str | None = None,
) -> None:
    """Insert or replace the summary for a given week."""
    week = week_label or _week_label()
    sql  = """
        INSERT INTO weekly_summary
            (week_label, top_keywords, github_summary, blog_summary, ai_news_summary, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_label) DO UPDATE SET
            top_keywords    = excluded.top_keywords,
            github_summary  = excluded.github_summary,
            blog_summary    = excluded.blog_summary,
            ai_news_summary = excluded.ai_news_summary,
            created_at      = excluded.created_at
    """
    with _get_conn() as conn:
        conn.execute(sql, (week, top_keywords, github_summary, blog_summary,
                           ai_news_summary, datetime.datetime.utcnow().isoformat()))
    logger.info(f"Saved weekly summary for {week}")


def fetch_weekly_summary(week_label: str | None = None) -> dict | None:
    week = week_label or _week_label()
    sql  = "SELECT * FROM weekly_summary WHERE week_label = ?"
    with _get_conn() as conn:
        row = conn.execute(sql, (week,)).fetchone()
    return dict(row) if row else None


def fetch_all_summaries() -> list[dict]:
    sql = "SELECT * FROM weekly_summary ORDER BY week_label DESC"
    with _get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def fetch_available_weeks() -> list[str]:
    """Return all week_labels present in the github_trends table, newest first."""
    sql = "SELECT DISTINCT week_label FROM github_trends ORDER BY week_label DESC"
    with _get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


# ── Bootstrap ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("DB ready at", DB_PATH)
