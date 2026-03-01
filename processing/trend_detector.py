"""
processing/trend_detector.py
─────────────────────────────
Detects trending keywords and topics from the scraped data.

Strategy
--------
1. Collect all text (repo descriptions + blog titles/summaries + AI news
   titles/summaries) for the current week.
2. Clean & tokenize.
3. Run TF-IDF to score each term across the corpus.
4. Aggregate scores and return the top-N keywords with their weights.

The function also produces simple per-category keyword lists so the
dashboard can show "top Python libraries this week" etc.
"""

import re
import json
import string
from collections import Counter
from typing import NamedTuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from loguru import logger

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import TOP_N_KEYWORDS, MIN_WORD_LENGTH

# ── Stopwords ─────────────────────────────────────────────────────────────────
# Use NLTK if available, fall back to a hand-crafted set.
try:
    import nltk
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    from nltk.corpus import stopwords as _nltk_sw
    _STOPWORDS = set(_nltk_sw.words("english"))
except Exception:
    _STOPWORDS = set()

# Extra domain-specific noise words
_EXTRA_STOP = {
    "github", "http", "https", "www", "com", "org", "io", "new", "use",
    "using", "used", "like", "also", "make", "made", "get", "got", "one",
    "two", "based", "via", "free", "open", "source", "project", "tool",
    "build", "built", "built-in", "support", "supports", "add", "added",
    "update", "updated", "version", "release", "blog", "post", "read",
    "more", "week", "year", "day", "time", "way", "set", "part", "work",
}
STOPWORDS = _STOPWORDS | _EXTRA_STOP


# ── Text cleaning ─────────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Lower-case, remove URLs, punctuation, digits."""
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)   # remove URLs
    text = re.sub(r"[0-9]+", " ", text)
    text = text.translate(str.maketrans(string.punctuation, " " * len(string.punctuation)))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> list[str]:
    """Return meaningful tokens from cleaned text."""
    tokens = _clean_text(text).split()
    return [
        t for t in tokens
        if len(t) >= MIN_WORD_LENGTH and t not in STOPWORDS
    ]


# ── TF-IDF analysis ───────────────────────────────────────────────────────────

class TrendResult(NamedTuple):
    keyword   : str
    score     : float
    frequency : int


def compute_tfidf_keywords(
    documents: list[str],
    top_n: int = TOP_N_KEYWORDS,
) -> list[TrendResult]:
    """
    Run TF-IDF on `documents` and return the top-N keywords ranked by their
    mean TF-IDF score across the corpus.

    Parameters
    ----------
    documents : list[str]  – each element is a piece of text (title + summary)
    top_n     : int        – how many keywords to return

    Returns
    -------
    list[TrendResult] sorted descending by score
    """
    if not documents:
        logger.warning("trend_detector: no documents supplied")
        return []

    # Clean documents
    cleaned = [_clean_text(doc) for doc in documents]
    cleaned = [d for d in cleaned if d.strip()]     # drop empty strings

    if not cleaned:
        return []

    vectorizer = TfidfVectorizer(
        max_features  = 5000,
        ngram_range   = (1, 2),     # unigrams + bigrams
        sublinear_tf  = True,
        min_df        = 2,           # ignore terms appearing < 2 docs
        stop_words    = list(STOPWORDS),
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(cleaned)
    except ValueError as exc:
        logger.warning(f"TF-IDF fit failed: {exc}")
        return _fallback_frequency(documents, top_n)

    feature_names = vectorizer.get_feature_names_out()
    mean_scores   = tfidf_matrix.mean(axis=0).A1   # average score per term

    # Build frequency count for display
    all_tokens = []
    for doc in cleaned:
        all_tokens.extend(doc.split())
    freq_counter = Counter(all_tokens)

    # Zip names with scores
    scored = sorted(
        zip(feature_names, mean_scores),
        key=lambda x: x[1],
        reverse=True,
    )

    results = []
    for term, score in scored[:top_n]:
        freq = sum(freq_counter.get(t, 0) for t in term.split())
        results.append(TrendResult(keyword=term, score=round(float(score), 4), frequency=freq))

    return results


def _fallback_frequency(documents: list[str], top_n: int) -> list[TrendResult]:
    """Simple word-frequency fallback when TF-IDF fails (e.g. tiny corpus)."""
    counter: Counter = Counter()
    for doc in documents:
        counter.update(_tokenize(doc))
    return [
        TrendResult(keyword=word, score=round(count / max(counter.values(), default=1), 4), frequency=count)
        for word, count in counter.most_common(top_n)
    ]


# ── Per-category helpers ──────────────────────────────────────────────────────

def _docs_from_repos(repos: list[dict]) -> list[str]:
    return [
        f"{r.get('name', '')} {r.get('description', '')} {r.get('language', '')}"
        for r in repos
    ]


def _docs_from_articles(articles: list[dict]) -> list[str]:
    return [
        f"{a.get('title', '')} {a.get('summary', '')}"
        for a in articles
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def detect_trends(
    repos    : list[dict],
    blogs    : list[dict],
    ai_news  : list[dict],
    top_n    : int = TOP_N_KEYWORDS,
) -> dict:
    """
    Run trend detection over all three data sources.

    Returns
    -------
    dict with keys:
        overall      : list[dict]  – top keywords across everything
        github       : list[dict]  – top keywords from repos
        blogs        : list[dict]  – top keywords from blog posts
        ai_news      : list[dict]  – top keywords from AI news
        top_languages: list[dict]  – {language, count} sorted by count
        keywords_json: str         – JSON array of top keywords (for DB storage)
    """
    logger.info("Detecting trends …")

    # ── All sources combined ──────────────────────────────────────────────────
    all_docs = (
        _docs_from_repos(repos)
        + _docs_from_articles(blogs)
        + _docs_from_articles(ai_news)
    )
    overall = compute_tfidf_keywords(all_docs, top_n=top_n)

    # ── Per-category ─────────────────────────────────────────────────────────
    github_kw = compute_tfidf_keywords(_docs_from_repos(repos),         top_n=top_n)
    blog_kw   = compute_tfidf_keywords(_docs_from_articles(blogs),      top_n=top_n)
    ai_kw     = compute_tfidf_keywords(_docs_from_articles(ai_news),    top_n=top_n)

    # ── Top programming languages ─────────────────────────────────────────────
    lang_counter: Counter = Counter(
        r.get("language", "Unknown")
        for r in repos
        if r.get("language") and r["language"].lower() not in ("unknown", "")
    )
    top_languages = [
        {"language": lang, "count": cnt}
        for lang, cnt in lang_counter.most_common(15)
    ]

    # ── Serialise for DB ──────────────────────────────────────────────────────
    keywords_json = json.dumps([kw.keyword for kw in overall[:20]])

    def _to_list(results: list[TrendResult]) -> list[dict]:
        return [{"keyword": r.keyword, "score": r.score, "frequency": r.frequency}
                for r in results]

    output = {
        "overall"      : _to_list(overall),
        "github"       : _to_list(github_kw),
        "blogs"        : _to_list(blog_kw),
        "ai_news"      : _to_list(ai_kw),
        "top_languages": top_languages,
        "keywords_json": keywords_json,
    }

    logger.success(f"Top 5 overall keywords: {[k['keyword'] for k in output['overall'][:5]]}")
    return output


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_repos = [
        {"name": "llama3", "description": "Large language model", "language": "Python"},
        {"name": "mistral", "description": "Efficient transformer model", "language": "Python"},
        {"name": "rust-async", "description": "Async runtime for Rust", "language": "Rust"},
    ]
    sample_blogs = [
        {"title": "GPT-5 announced", "summary": "OpenAI releases GPT-5 model"},
        {"title": "Rust in production", "summary": "Companies adopt Rust for systems"},
    ]
    result = detect_trends(sample_repos, sample_blogs, [])
    print("Overall keywords:", result["overall"][:5])
    print("Top languages   :", result["top_languages"])
