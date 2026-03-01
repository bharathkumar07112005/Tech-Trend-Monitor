"""
processing/summarizer.py
────────────────────────
Provides two summarisation strategies:

1. Extractive (default, zero extra deps beyond NLTK)
   – Scores sentences by TF-IDF-style word importance and picks the top N.

2. Transformer-based (optional – requires `transformers` + `torch`)
   – Uses sshleifer/distilbart-cnn-12-6 (small, fast BART variant).
   – Enable by setting USE_TRANSFORMER_SUMMARY=true in .env

Both strategies expose the same interface:
    summarize(text: str) -> str
"""

import re
from loguru import logger

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from config import EXTRACTIVE_SENTENCES, USE_TRANSFORMER_SUMMARY, TRANSFORMER_MODEL

# ── NLTK setup ────────────────────────────────────────────────────────────────
try:
    import nltk
    for resource in ("punkt", "stopwords", "punkt_tab"):
        try:
            nltk.data.find(f"tokenizers/{resource}" if resource.startswith("punkt") else f"corpora/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords as _sw
    _STOP = set(_sw.words("english"))
    _NLTK_OK = True
except Exception as exc:
    logger.warning(f"NLTK not fully available ({exc}); using basic sentence splitting")
    _NLTK_OK = False
    _STOP = set()


# ── Sentence splitter fallback ────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    if _NLTK_OK:
        return sent_tokenize(text)
    # Very basic fallback: split on ". " boundaries
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


# ═════════════════════════════════════════════════════════════════════════════
# OPTION 1: Extractive summarisation
# ═════════════════════════════════════════════════════════════════════════════

def _word_frequencies(text: str) -> dict[str, float]:
    """Return normalised frequency for every non-stop word in text."""
    words = re.findall(r"\b[a-z]+\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOP and len(w) > 2:
            freq[w] = freq.get(w, 0) + 1
    if not freq:
        return {}
    max_f = max(freq.values())
    return {w: c / max_f for w, c in freq.items()}


def extractive_summarize(text: str, n_sentences: int = EXTRACTIVE_SENTENCES) -> str:
    """
    Score each sentence by the sum of its word-frequency scores and return
    the top `n_sentences` in original order.
    """
    if not text or not text.strip():
        return ""

    sentences = _split_sentences(text)
    if len(sentences) <= n_sentences:
        return text.strip()

    freq = _word_frequencies(text)

    # Score each sentence
    scored: list[tuple[int, float, str]] = []
    for idx, sent in enumerate(sentences):
        words = re.findall(r"\b[a-z]+\b", sent.lower())
        score = sum(freq.get(w, 0) for w in words)
        scored.append((idx, score, sent))

    # Pick top sentences, restore original order
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:n_sentences]
    top.sort(key=lambda x: x[0])

    return " ".join(s for _, _, s in top)


# ═════════════════════════════════════════════════════════════════════════════
# OPTION 2: Transformer summarisation
# ═════════════════════════════════════════════════════════════════════════════

_pipeline = None   # lazy-loaded

def _load_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    try:
        from transformers import pipeline as hf_pipeline
        logger.info(f"Loading HuggingFace summarisation model: {TRANSFORMER_MODEL}")
        _pipeline = hf_pipeline("summarization", model=TRANSFORMER_MODEL)
        logger.success("Transformer pipeline ready")
    except Exception as exc:
        logger.error(f"Could not load transformer pipeline: {exc}")
        _pipeline = None
    return _pipeline


def transformer_summarize(text: str, max_length: int = 150, min_length: int = 40) -> str:
    """
    Summarise text using a small BART transformer.
    Falls back to extractive summarisation if the model isn't available.
    """
    pipe = _load_pipeline()
    if pipe is None:
        logger.warning("Transformer unavailable; falling back to extractive summarisation")
        return extractive_summarize(text)

    # BART has a 1024 token limit — truncate input text conservatively
    truncated = text[:3000]
    try:
        result = pipe(truncated, max_length=max_length, min_length=min_length, do_sample=False)
        return result[0]["summary_text"].strip()
    except Exception as exc:
        logger.warning(f"Transformer inference failed: {exc}; falling back to extractive")
        return extractive_summarize(text)


# ═════════════════════════════════════════════════════════════════════════════
# Public interface
# ═════════════════════════════════════════════════════════════════════════════

def summarize(text: str, **kwargs) -> str:
    """
    Route to the appropriate summarisation strategy based on config.
    Always returns a non-empty string (or empty string if `text` is empty).
    """
    if not text or not text.strip():
        return ""
    if USE_TRANSFORMER_SUMMARY:
        return transformer_summarize(text, **kwargs)
    return extractive_summarize(text, **kwargs)


# ─── High-level helpers used by main.py ───────────────────────────────────────

def summarize_github_trends(repos: list[dict]) -> str:
    """
    Build a human-readable paragraph summarising this week's trending repos.
    """
    if not repos:
        return "No GitHub trending data available for this period."

    top = repos[:10]
    lines = [
        f"{r['name']} ({r.get('language','?')}, ⭐ {r.get('stars_today', 0)} today)"
        for r in top
    ]
    intro = (
        f"This week's top {len(top)} trending GitHub repositories include: "
        + ", ".join(lines[:5]) + ". "
    )
    # Collect all descriptions for deeper summarisation
    descriptions = " ".join(r.get("description", "") for r in top if r.get("description"))
    body = summarize(descriptions) if descriptions else ""
    return (intro + body).strip()


def summarize_blog_posts(posts: list[dict]) -> str:
    if not posts:
        return "No blog posts available for this period."

    combined = " ".join(
        f"{p.get('title', '')}. {p.get('summary', '')}" for p in posts[:30]
    )
    return summarize(combined) or "Unable to generate blog summary."


def summarize_ai_news(articles: list[dict]) -> str:
    if not articles:
        return "No AI news available for this period."

    combined = " ".join(
        f"{a.get('title', '')}. {a.get('summary', '')}" for a in articles[:30]
    )
    return summarize(combined) or "Unable to generate AI news summary."


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = (
        "OpenAI released GPT-5 today, marking a major leap in AI capabilities. "
        "The new model excels at reasoning and code generation. "
        "Google DeepMind also announced Gemini Ultra 2 with improved multimodal support. "
        "Meanwhile, Meta open-sourced Llama 3 under a permissive license, enabling "
        "developers worldwide to fine-tune the model for custom applications. "
        "Researchers at Stanford demonstrated that smaller models can achieve "
        "comparable performance through better data curation and fine-tuning techniques."
    )
    print("Extractive:")
    print(extractive_summarize(sample, n_sentences=2))
