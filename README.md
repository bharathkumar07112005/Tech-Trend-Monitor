# 🚀 Tech Trend Monitor

An automated system that scrapes GitHub trending repos, tech blogs, and AI news —
then detects weekly trends, generates NLP summaries, displays a live dashboard,
and sends polished HTML email reports.

---

## 📁 Project Structure

```
tech_trend_monitor/
├── scraper/
│   ├── github_scraper.py      # GitHub trending scraper (all languages)
│   ├── blog_scraper.py        # Tech blog RSS feed scraper
│   └── ai_news_scraper.py     # AI-specific RSS scraper
├── processing/
│   ├── trend_detector.py      # TF-IDF keyword trend detection
│   └── summarizer.py          # Extractive + optional transformer summarisation
├── database/
│   └── db_manager.py          # SQLite wrapper (insert / fetch / upsert)
├── dashboard/
│   └── app.py                 # Streamlit dashboard
├── notifier/
│   └── email_sender.py        # HTML email via SMTP
├── scheduler/
│   └── weekly_job.py          # schedule-based weekly runner
├── config.py                  # Central config (reads .env)
├── main.py                    # Pipeline orchestrator
├── requirements.txt
└── .env.example               # Copy to .env and fill in
```

---

## ⚙️ Installation

### 1 · Prerequisites

- Python 3.10 or higher
- pip

### 2 · Clone / download the project

```bash
git clone https://github.com/yourname/tech-trend-monitor.git
cd tech_trend_monitor
```

### 3 · Create a virtual environment (recommended)

```bash
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 4 · Install dependencies

```bash
pip install -r requirements.txt
```

### 5 · Download NLTK data (one-time)

```bash
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('punkt_tab')"
```

### 6 · Configure environment

```bash
cp .env.example .env
# Open .env with your editor and fill in SMTP credentials if you want email reports
```

---

## 🚀 Running Locally

### Run the full pipeline once

```bash
python main.py
```

This will:
1. Scrape GitHub trending
2. Scrape tech blogs + AI news RSS feeds
3. Store data in `data/tech_trends.db`
4. Detect trends
5. Generate summaries
6. Send email (if `EMAIL_ENABLED=true`)

### Run the pipeline without sending email

```bash
python main.py --no-email
```

### Dry run (scrape + print only, no DB or email)

```bash
python main.py --dry-run
```

### Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open your browser at **http://localhost:8501**

---

## 📅 Weekly Scheduling

### Option A — Python scheduler (always-on process)

```bash
# Start the scheduler process (blocks forever, runs every Monday 08:00)
python -m scheduler.weekly_job

# Trigger immediately + start scheduler
python -m scheduler.weekly_job --run-now
```

Change the schedule in `.env` or `config.py`:
```python
SCHEDULE_DAY  = "monday"
SCHEDULE_TIME = "08:00"
```

### Option B — System cron (Linux / macOS)

```bash
crontab -e
```

Add this line to run every Monday at 8 AM:
```cron
0 8 * * 1 /path/to/tech_trend_monitor/.venv/bin/python /path/to/tech_trend_monitor/main.py >> /path/to/tech_trend_monitor/logs/cron.log 2>&1
```

### Option C — Windows Task Scheduler

1. Open Task Scheduler → Create Basic Task
2. Trigger: Weekly, Monday, 08:00
3. Action: Start a program
4. Program: `C:\path\to\.venv\Scripts\python.exe`
5. Arguments: `C:\path\to\tech_trend_monitor\main.py`

---

## 📧 Email Setup (Gmail)

Gmail blocks plain password auth. You must use an **App Password**:

1. Enable 2-Step Verification on your Google account
2. Go to **myaccount.google.com/apppasswords**
3. Generate a password for "Mail"
4. Copy it into your `.env`:

```env
EMAIL_ENABLED=true
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx    # 16-char app password (spaces ok)
EMAIL_FROM=you@gmail.com
EMAIL_TO=recipient@example.com
```

---

## 🤖 Advanced Summarisation (HuggingFace)

By default the project uses fast **extractive** summarisation (no GPU needed).
To enable transformer-based summarisation:

1. Uncomment in `requirements.txt`:
   ```
   transformers==4.39.3
   torch==2.2.1
   ```
2. Re-install: `pip install -r requirements.txt`
3. Set in `.env`: `USE_TRANSFORMER_SUMMARY=true`

The model (`distilbart-cnn-12-6`) will be downloaded automatically (~900 MB).

---

## 🗃️ Database

SQLite database at `data/tech_trends.db`.

| Table            | Contents                                  |
|------------------|-------------------------------------------|
| `github_trends`  | Repo name, stars, language, description   |
| `blog_posts`     | Title, URL, summary, source               |
| `ai_news`        | Title, URL, summary, release flag         |
| `weekly_summary` | Summaries + keywords per ISO week         |

Browse with any SQLite viewer (e.g. DB Browser for SQLite).

---

## 🛠 Common Errors & Fixes

| Error | Fix |
|---|---|
| `ModuleNotFoundError: feedparser` | Run `pip install -r requirements.txt` |
| `LookupError: Resource punkt not found` | Run `python -c "import nltk; nltk.download('punkt')"` |
| `SMTPAuthenticationError` | Use Gmail App Password, not your regular password |
| `Connection refused` to SMTP | Check `SMTP_HOST` / `SMTP_PORT`; Gmail uses `smtp.gmail.com:587` |
| Dashboard shows "No data yet" | Run `python main.py` first |
| GitHub scraper returns 0 repos | GitHub may have changed HTML; check for lxml/bs4 update |
| `requests.exceptions.ReadTimeout` | Increase `REQUEST_TIMEOUT` in `config.py` |
| Transformer model download fails | Check internet connection; model needs ~900 MB disk |

---

## 🔧 Customising

**Add a new blog feed** — edit `config.py`:
```python
BLOG_RSS_FEEDS["My Blog"] = "https://myblog.com/feed.xml"
```

**Add a new AI news feed**:
```python
AI_NEWS_FEEDS["My AI Source"] = "https://ai-source.com/rss"
```

**Change trending languages**:
```python
GITHUB_LANGUAGES = ["python", "rust", "go", "zig", "kotlin", ""]
```

**Change top-N keywords**:
```python
TOP_N_KEYWORDS = 50
```

---

## 📊 Dashboard Features

- Week selector (compare any past week)
- KPI cards: repo count, blog count, AI news count
- Trending keyword badges (TF-IDF powered)
- Repo table with language filter
- Stars-today bar chart (top 10)
- Language distribution (pie + bar)
- AI news feed with release filter
- Blog posts feed with source filter
- NLP-generated summaries per category
- Historical trend line chart (multi-week)
- "Run Pipeline Now" button

---

## 📜 License

MIT — use freely, attribute appreciated.
