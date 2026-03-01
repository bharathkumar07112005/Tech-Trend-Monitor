"""
dashboard/app.py
────────────────
Streamlit dashboard for Tech Trend Monitor.

Run:
    streamlit run dashboard/app.py
"""

import json
import sys
import datetime
import pathlib

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import DASHBOARD_TITLE
from database.db_manager import (
    init_db,
    fetch_github_repos,
    fetch_blog_posts,
    fetch_ai_news,
    fetch_weekly_summary,
    fetch_available_weeks,
    fetch_all_summaries,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Dark gradient header */
  .stApp { background-color: #0F172A; }
  section[data-testid="stSidebar"] { background-color: #1E293B; }

  /* Metric cards */
  div[data-testid="stMetric"] {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px;
  }
  div[data-testid="stMetric"] label { color: #94A3B8 !important; }
  div[data-testid="stMetric"] div   { color: #F1F5F9 !important; }

  /* Table headers */
  th { background: #1E293B !important; color: #94A3B8 !important; }

  /* Keyword badges */
  .kw-badge {
    display: inline-block;
    background: #1E293B;
    border: 1px solid #334155;
    color: #38BDF8;
    border-radius: 20px;
    padding: 4px 12px;
    margin: 3px;
    font-size: 13px;
    font-weight: 500;
  }

  /* Section card */
  .section-card {
    background: #1E293B;
    border-radius: 10px;
    border: 1px solid #334155;
    padding: 20px;
    margin-bottom: 16px;
  }

  /* Summary text */
  .summary-text {
    color: #CBD5E1;
    font-size: 14px;
    line-height: 1.75;
  }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)   # cache for 5 minutes
def _load_data(week_label: str):
    repos   = fetch_github_repos(week_label=week_label, limit=50)
    posts   = fetch_blog_posts  (week_label=week_label, limit=100)
    news    = fetch_ai_news     (week_label=week_label, limit=100)
    summary = fetch_weekly_summary(week_label=week_label)
    return repos, posts, news, summary


def _parse_keywords(summary: dict | None) -> list[str]:
    if not summary:
        return []
    try:
        return json.loads(summary.get("top_keywords", "[]"))
    except Exception:
        return []


def _current_week() -> str:
    d = datetime.datetime.utcnow()
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🚀 Tech Trend Monitor")
    st.markdown("---")

    # Ensure DB exists
    init_db()

    # Week selector
    available_weeks = fetch_available_weeks()
    current_week    = _current_week()

    if available_weeks:
        selected_week = st.selectbox(
            "📅 Select Week",
            options=available_weeks,
            index=0,
            help="ISO week label (e.g. 2024-W12)",
        )
    else:
        selected_week = current_week
        st.info("No data yet. Run `python main.py` to collect data.")

    st.markdown("---")

    # Category filter
    st.markdown("### 🔽 Filters")
    show_github = st.checkbox("GitHub Trends",  value=True)
    show_blogs  = st.checkbox("Tech Blogs",     value=True)
    show_ai     = st.checkbox("AI News",        value=True)

    # Language filter
    st.markdown("---")
    st.markdown("### 🌐 Language Filter")

    # Run pipeline button
    st.markdown("---")
    if st.button("▶ Run Pipeline Now", use_container_width=True, type="primary"):
        with st.spinner("Running pipeline … (this may take 1-2 min)"):
            try:
                from main import run_pipeline
                run_pipeline()
                st.cache_data.clear()
                st.success("Pipeline complete!")
                st.rerun()
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    st.markdown("---")
    st.caption("Tech Trend Monitor v1.0")


# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────

repos, posts, news, summary = _load_data(selected_week)

# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="background:linear-gradient(135deg,#1D4ED8 0%,#7C3AED 100%);
            border-radius:12px;padding:28px 32px;margin-bottom:24px;">
  <h1 style="margin:0;color:#fff;font-size:28px;">🚀 Tech Trend Monitor</h1>
  <p style="margin:6px 0 0;color:#BFDBFE;font-size:15px;">
    Weekly Intelligence Dashboard · <strong>{selected_week}</strong>
  </p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# KPI row
# ─────────────────────────────────────────────────────────────────────────────

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Trending Repos",   len(repos))
c2.metric("📰 Blog Articles",    len(posts))
c3.metric("🤖 AI News Articles", len(news))
c4.metric("📅 Week",             selected_week)

st.markdown("")   # spacer


# ─────────────────────────────────────────────────────────────────────────────
# Trending Keywords
# ─────────────────────────────────────────────────────────────────────────────

keywords = _parse_keywords(summary)

with st.container():
    st.markdown("### 🔥 Trending Keywords This Week")
    if keywords:
        badges = "".join(f'<span class="kw-badge">{kw}</span>' for kw in keywords)
        st.markdown(f'<div style="margin-bottom:8px;">{badges}</div>', unsafe_allow_html=True)
    else:
        st.info("No keyword data — run the pipeline first.")


st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Trending Repositories
# ─────────────────────────────────────────────────────────────────────────────

if show_github:
    st.markdown("### 📦 Trending GitHub Repositories")

    if repos:
        df_repos = pd.DataFrame(repos)

        # Language multi-select
        all_langs = sorted(df_repos["language"].dropna().unique().tolist())
        sel_langs = st.multiselect(
            "Filter by language",
            options=all_langs,
            default=[],
            placeholder="All languages",
        )
        if sel_langs:
            df_repos = df_repos[df_repos["language"].isin(sel_langs)]

        col_left, col_right = st.columns([3, 2])

        with col_left:
            # Repo table
            display_df = df_repos[["rank", "name", "language", "stars_today", "total_stars", "description"]].copy()
            display_df.columns = ["#", "Repository", "Language", "⭐ Today", "⭐ Total", "Description"]
            display_df["Description"] = display_df["Description"].str[:80] + "…"
            st.dataframe(display_df, use_container_width=True, hide_index=True)

        with col_right:
            # Stars today bar chart (top 10)
            top10 = df_repos.head(10)
            fig = px.bar(
                top10,
                x="stars_today",
                y="name",
                orientation="h",
                color="stars_today",
                color_continuous_scale="Blues",
                labels={"stars_today": "Stars Today", "name": "Repository"},
                title="Top 10 by Stars Today",
            )
            fig.update_layout(
                plot_bgcolor  = "#0F172A",
                paper_bgcolor = "#1E293B",
                font_color    = "#CBD5E1",
                showlegend    = False,
                coloraxis_showscale=False,
                margin        = dict(l=10, r=10, t=40, b=10),
            )
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(fig, use_container_width=True)

        # Summary
        if summary and summary.get("github_summary"):
            st.markdown(
                f'<div class="section-card"><p class="summary-text">'
                f'<strong>📝 Summary:</strong> {summary["github_summary"]}</p></div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No GitHub data for this week.")

    st.markdown("")


# ─────────────────────────────────────────────────────────────────────────────
# Programming Languages Chart
# ─────────────────────────────────────────────────────────────────────────────

if repos:
    st.markdown("### 💻 Programming Languages Distribution")
    df_lang = (
        pd.DataFrame(repos)
        .groupby("language", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values("count", ascending=False)
        .head(12)
    )

    col_pie, col_bar = st.columns(2)

    with col_pie:
        fig_pie = px.pie(
            df_lang, names="language", values="count",
            title="Share by Repository Count",
            color_discrete_sequence=px.colors.sequential.Blues_r,
            hole=0.45,
        )
        fig_pie.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="#1E293B",
        font_color="#CBD5E1", 
        margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_bar:
        fig_bar = px.bar(
            df_lang, x="count", y="language",
            orientation="h",
            color="count",
            color_continuous_scale="Viridis",
            title="Repository Count per Language",
            labels={"count": "Count", "language": "Language"},
        )
        fig_bar.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", 
        paper_bgcolor="#1E293B",
        font_color="#CBD5E1",
        showlegend=False, 
        coloraxis_showscale=False,
        margin=dict(l=10, r=10, t=40, b=10),
    )
        fig_bar.update_yaxes(categoryorder="total ascending")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# AI News
# ─────────────────────────────────────────────────────────────────────────────

if show_ai:
    st.markdown("### 🤖 AI News Highlights")

    if news:
        df_news = pd.DataFrame(news)

        # Release filter
        show_releases_only = st.checkbox("Show AI releases / announcements only", value=False)
        if show_releases_only:
            df_news = df_news[df_news["is_release"] == 1]

        # Source filter
        sources   = sorted(df_news["source"].dropna().unique().tolist())
        sel_src   = st.multiselect("Filter by source", sources, default=[], placeholder="All sources")
        if sel_src:
            df_news = df_news[df_news["source"].isin(sel_src)]

        # Display
        for _, row in df_news.head(20).iterrows():
            release_badge = "🚀 " if row.get("is_release") else ""
            st.markdown(
                f'<div class="section-card">'
                f'<strong style="color:#F1F5F9;">{release_badge}{row["title"]}</strong><br>'
                f'<small style="color:#64748B;">{row["source"]} · {row["published_at"][:10]}</small><br>'
                f'<span class="summary-text">{row.get("summary","")[:300]}</span><br>'
                f'<a href="{row.get("url","#")}" style="color:#38BDF8;font-size:12px;" target="_blank">Read more →</a>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if summary and summary.get("ai_news_summary"):
            st.markdown(
                f'<div class="section-card" style="border-color:#7C3AED;">'
                f'<strong style="color:#A78BFA;">📝 AI News Summary:</strong>'
                f'<p class="summary-text">{summary["ai_news_summary"]}</p></div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No AI news for this week.")

    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Tech Blog Posts
# ─────────────────────────────────────────────────────────────────────────────

if show_blogs:
    st.markdown("### 📰 Tech Blog Posts")

    if posts:
        df_posts = pd.DataFrame(posts)
        sources  = sorted(df_posts["source"].dropna().unique().tolist())
        sel_blog = st.multiselect("Filter by blog", sources, default=[], placeholder="All blogs", key="blog_src")
        if sel_blog:
            df_posts = df_posts[df_posts["source"].isin(sel_blog)]

        for _, row in df_posts.head(20).iterrows():
            st.markdown(
                f'<div class="section-card">'
                f'<strong style="color:#F1F5F9;">{row["title"]}</strong><br>'
                f'<small style="color:#64748B;">{row["source"]} · {row["published_at"][:10]}</small><br>'
                f'<span class="summary-text">{row.get("summary","")[:300]}</span><br>'
                f'<a href="{row.get("url","#")}" style="color:#38BDF8;font-size:12px;" target="_blank">Read more →</a>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if summary and summary.get("blog_summary"):
            st.markdown(
                f'<div class="section-card" style="border-color:#059669;">'
                f'<strong style="color:#34D399;">📝 Blog Summary:</strong>'
                f'<p class="summary-text">{summary["blog_summary"]}</p></div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No blog posts for this week.")

    st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# Historical Trends (multi-week)
# ─────────────────────────────────────────────────────────────────────────────

all_summaries = fetch_all_summaries()

if len(all_summaries) >= 2:
    st.markdown("### 📈 Historical Activity")

    hist_data = []
    for s in all_summaries:
        week   = s["week_label"]
        r_cnt  = len(fetch_github_repos(week_label=week))
        b_cnt  = len(fetch_blog_posts(week_label=week))
        n_cnt  = len(fetch_ai_news(week_label=week))
        hist_data.append({"Week": week, "Repos": r_cnt, "Blog Posts": b_cnt, "AI News": n_cnt})

    df_hist = pd.DataFrame(hist_data).sort_values("Week")

    fig_hist = go.Figure()
    for col, colour in [("Repos","#38BDF8"), ("Blog Posts","#34D399"), ("AI News","#F472B6")]:
        fig_hist.add_trace(go.Scatter(
            x=df_hist["Week"], y=df_hist[col],
            name=col, mode="lines+markers",
            line=dict(color=colour, width=2),
            marker=dict(size=6),
        ))
    fig_hist.update_layout(
        plot_bgcolor="#0F172A", paper_bgcolor="#1E293B",
        font_color="#CBD5E1",
        xaxis=dict(gridcolor="#334155"),
        yaxis=dict(gridcolor="#334155"),
        legend=dict(bgcolor="#1E293B", bordercolor="#334155"),
        margin=dict(l=10, r=10, t=20, b=10),
    )
    st.plotly_chart(fig_hist, use_container_width=True)
