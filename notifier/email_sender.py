"""
notifier/email_sender.py
─────────────────────────
Sends a beautifully formatted HTML weekly report via SMTP (Gmail-ready).

Usage
-----
    from notifier.email_sender import send_weekly_report
    send_weekly_report(summary_data, trend_data)

The email is only sent when EMAIL_ENABLED=true in config / .env.
"""

import json
import smtplib
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.utils          import formatdate

from loguru import logger

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import (
    EMAIL_ENABLED, SMTP_HOST, SMTP_PORT,
    SMTP_USER, SMTP_PASSWORD,
    EMAIL_FROM, EMAIL_TO,
)


# ── HTML Template ─────────────────────────────────────────────────────────────

def _build_html(
    week_label      : str,
    top_keywords    : list[str],
    github_summary  : str,
    blog_summary    : str,
    ai_news_summary : str,
    top_repos       : list[dict],
    top_languages   : list[dict],
) -> str:
    """Render the full HTML email body."""

    # Keywords badges
    kw_badges = "".join(
        f'<span style="display:inline-block;background:#1E293B;color:#38BDF8;'
        f'border-radius:4px;padding:3px 10px;margin:3px;font-size:12px;">{kw}</span>'
        for kw in top_keywords[:15]
    )

    # Repo rows
    repo_rows = "".join(
        f"""<tr style="border-bottom:1px solid #334155;">
              <td style="padding:8px;color:#94A3B8;">{i}</td>
              <td style="padding:8px;">
                <a href="{r.get('url','#')}" style="color:#38BDF8;text-decoration:none;font-weight:600;">
                  {r.get('name','?')}
                </a><br>
                <small style="color:#94A3B8;">{r.get('description','')[:120]}</small>
              </td>
              <td style="padding:8px;color:#4ADE80;text-align:center;">⭐ {r.get('stars_today',0):,}</td>
              <td style="padding:8px;color:#F472B6;text-align:center;">{r.get('language','?')}</td>
            </tr>"""
        for i, r in enumerate(top_repos[:10], 1)
    )

    # Language bars
    max_count = max((l["count"] for l in top_languages), default=1)
    lang_bars = "".join(
        f"""<div style="margin:4px 0;">
              <span style="display:inline-block;width:110px;color:#CBD5E1;font-size:13px;">{l['language']}</span>
              <span style="display:inline-block;width:{int(l['count']/max_count*180)}px;
                    height:14px;background:#38BDF8;border-radius:2px;vertical-align:middle;"></span>
              <span style="color:#94A3B8;font-size:12px;margin-left:6px;">{l['count']}</span>
            </div>"""
        for l in top_languages[:10]
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tech Trend Monitor – {week_label}</title></head>
<body style="margin:0;padding:0;background:#0F172A;font-family:'Segoe UI',Arial,sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0F172A;padding:30px 0;">
  <tr><td align="center">
  <table width="640" cellpadding="0" cellspacing="0" style="background:#1E293B;border-radius:12px;overflow:hidden;">

    <!-- Header -->
    <tr><td style="background:linear-gradient(135deg,#1D4ED8,#7C3AED);padding:32px 40px;text-align:center;">
      <h1 style="margin:0;color:#fff;font-size:26px;letter-spacing:-0.5px;">🚀 Tech Trend Monitor</h1>
      <p style="margin:8px 0 0;color:#BFDBFE;font-size:14px;">Weekly Report · {week_label}</p>
    </td></tr>

    <!-- Trending Keywords -->
    <tr><td style="padding:28px 40px;">
      <h2 style="color:#F1F5F9;font-size:18px;margin:0 0 14px;">🔥 Trending Keywords</h2>
      {kw_badges}
    </td></tr>

    <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;"></td></tr>

    <!-- GitHub Trends -->
    <tr><td style="padding:28px 40px;">
      <h2 style="color:#F1F5F9;font-size:18px;margin:0 0 14px;">📦 GitHub Trending Repositories</h2>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#0F172A;border-radius:8px;">
        <tr style="background:#334155;">
          <th style="padding:10px;color:#94A3B8;font-size:12px;text-align:left;">#</th>
          <th style="padding:10px;color:#94A3B8;font-size:12px;text-align:left;">Repository</th>
          <th style="padding:10px;color:#94A3B8;font-size:12px;">Stars Today</th>
          <th style="padding:10px;color:#94A3B8;font-size:12px;">Language</th>
        </tr>
        {repo_rows}
      </table>
      <div style="background:#0F172A;border-radius:8px;padding:16px;margin-top:14px;">
        <p style="color:#CBD5E1;font-size:14px;line-height:1.7;margin:0;">{github_summary}</p>
      </div>
    </td></tr>

    <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;"></td></tr>

    <!-- Top Languages -->
    <tr><td style="padding:28px 40px;">
      <h2 style="color:#F1F5F9;font-size:18px;margin:0 0 14px;">💻 Top Programming Languages</h2>
      {lang_bars}
    </td></tr>

    <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;"></td></tr>

    <!-- AI News -->
    <tr><td style="padding:28px 40px;">
      <h2 style="color:#F1F5F9;font-size:18px;margin:0 0 14px;">🤖 AI News Highlights</h2>
      <div style="background:#0F172A;border-radius:8px;padding:16px;">
        <p style="color:#CBD5E1;font-size:14px;line-height:1.7;margin:0;">{ai_news_summary}</p>
      </div>
    </td></tr>

    <tr><td style="padding:0 40px;"><hr style="border:none;border-top:1px solid #334155;"></td></tr>

    <!-- Blog Insights -->
    <tr><td style="padding:28px 40px;">
      <h2 style="color:#F1F5F9;font-size:18px;margin:0 0 14px;">📰 Tech Blog Insights</h2>
      <div style="background:#0F172A;border-radius:8px;padding:16px;">
        <p style="color:#CBD5E1;font-size:14px;line-height:1.7;margin:0;">{blog_summary}</p>
      </div>
    </td></tr>

    <!-- Footer -->
    <tr><td style="background:#0F172A;padding:20px 40px;text-align:center;border-top:1px solid #1E293B;">
      <p style="color:#475569;font-size:12px;margin:0;">
        Generated by Tech Trend Monitor · {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}<br>
        <a href="#" style="color:#38BDF8;">Unsubscribe</a>
      </p>
    </td></tr>

  </table>
  </td></tr>
  </table>
</body>
</html>"""

    return html


# ── Plain-text fallback ───────────────────────────────────────────────────────

def _build_plain(
    week_label      : str,
    top_keywords    : list[str],
    github_summary  : str,
    blog_summary    : str,
    ai_news_summary : str,
) -> str:
    kw_str = ", ".join(top_keywords[:15])
    return f"""Tech Trend Monitor – Weekly Report ({week_label})
{"=" * 55}

TRENDING KEYWORDS
{kw_str}

GITHUB TRENDS
{github_summary}

AI NEWS HIGHLIGHTS
{ai_news_summary}

TECH BLOG INSIGHTS
{blog_summary}

---
Generated by Tech Trend Monitor
"""


# ── Send ──────────────────────────────────────────────────────────────────────

def send_weekly_report(
    summary  : dict,
    trends   : dict,
    repos    : list[dict],
) -> bool:
    """
    Compose and send the weekly HTML email.

    Parameters
    ----------
    summary  : dict  – from db_manager.fetch_weekly_summary()
    trends   : dict  – from trend_detector.detect_trends()
    repos    : list  – from db_manager.fetch_github_repos()

    Returns
    -------
    True on success, False on failure.
    """
    if not EMAIL_ENABLED:
        logger.info("Email sending is disabled (EMAIL_ENABLED=false). Skipping.")
        return False

    if not SMTP_USER or not SMTP_PASSWORD:
        logger.error("SMTP credentials not configured. Set SMTP_USER and SMTP_PASSWORD in .env")
        return False

    week_label      = summary.get("week_label", "N/A")
    github_summary  = summary.get("github_summary", "")
    blog_summary    = summary.get("blog_summary", "")
    ai_news_summary = summary.get("ai_news_summary", "")

    raw_keywords    = summary.get("top_keywords", "[]")
    try:
        top_keywords = json.loads(raw_keywords)
    except Exception:
        top_keywords = []

    top_languages   = trends.get("top_languages", [])

    # Build message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 Tech Trend Monitor – {week_label}"
    msg["From"]    = EMAIL_FROM
    msg["To"]      = ", ".join(EMAIL_TO)
    msg["Date"]    = formatdate(localtime=True)

    plain = _build_plain(week_label, top_keywords, github_summary, blog_summary, ai_news_summary)
    html  = _build_html(week_label, top_keywords, github_summary, blog_summary,
                         ai_news_summary, repos, top_languages)

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    # Send via SMTP
    try:
        logger.info(f"Connecting to {SMTP_HOST}:{SMTP_PORT} …")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        logger.success(f"Weekly report sent to {EMAIL_TO}")
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed – check SMTP_USER and SMTP_PASSWORD (use an App Password for Gmail)")
    except Exception as exc:
        logger.error(f"Failed to send email: {exc}")
    return False
