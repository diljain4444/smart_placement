import asyncio
import hashlib
import json
import os
import re
import sys
import threading
import time
from calendar import timegm
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import feedparser
import requests
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field


# ============================================================
# 1. ENV
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env")


# ============================================================
# 2. SETTINGS
# ============================================================

TARGET_COMPANIES = [
    "Google", "Microsoft", "Amazon", "Meta", "Apple",
    "Nvidia", "OpenAI", "Anthropic", "TCS", "Infosys",
]

RSS_LIMIT = 12
MAX_ARTICLES_TO_LLM = 8

FETCH_TIMEOUT = 6          # seconds per RSS request
LLM_TIMEOUT = 30           # seconds per Groq request
LLM_CONCURRENCY = 10       # lower to 4-5 if you see Groq 429 errors

CACHE_FILE = "news_cache.json"
CACHE_TTL_SECONDS = 30 * 60


# ============================================================
# 3. SCHEMA
# ============================================================

class NewsItem(BaseModel):
    headline: str = Field(
        description="The main news headline rewritten clearly. Maximum 20 words."
    )
    published_date: str = Field(
        description="The exact published date from the input."
    )


class CompanyNews(BaseModel):
    company: str
    news: list[NewsItem] = Field(default_factory=list, max_length=6)


# ============================================================
# 4. MODEL
# ============================================================

# The client retries 429/5xx itself, so there is no manual retry loop.
# max_tokens includes reasoning tokens; too low truncates the JSON.
model = ChatGroq(
    model="openai/gpt-oss-20b",
    api_key=GROQ_API_KEY,
    temperature=0,
    reasoning_effort="low",
    max_tokens=1000,
    timeout=LLM_TIMEOUT,
    max_retries=2,
)

structured_model = model.with_structured_output(CompanyNews, method="json_schema")

LLM_SEMAPHORE = threading.Semaphore(LLM_CONCURRENCY)


# ============================================================
# 5. PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a news curator for an engineering college placement-preparation platform.
Extract only the MAIN placement-relevant company news from the supplied articles.

Company: {company}

News articles:
{news}

KEEP news about: hiring, recruitment, campus hiring, internships, fresher hiring,
layoffs, hiring freezes, workforce changes, new offices, expansion (incl. India),
leadership changes, salary/compensation changes, major business growth, major
funding/investment, major acquisitions/mergers, major restructuring, important
technology or product launches, major workplace changes.

REMOVE: stock/share-market news, entertainment, sports, opinions, ads, promotional
articles, duplicates, articles where the company is only mentioned incidentally,
and anything unrelated to the company's employees, hiring, business, expansion
or technology.

RULES:
1. Use ONLY the supplied title and published date. Never invent numbers, names,
   reasons, salaries, job counts, quotes or outcomes.
2. Keep the original meaning; rewrite the headline clearly if necessary.
3. Maximum 6 items, sorted newest to oldest.
4. If several articles describe the same event, keep only one.
5. Keep the exact published date from the input.
6. Return only genuinely important placement-related news. Do not create news
   just because an article contains a keyword.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Extract the relevant main news using the required structure."),
    ]
)


# ============================================================
# 6. CACHE (per company, thread-safe, atomic file writes)
# ============================================================

_cache_lock = threading.Lock()


def _load_cache() -> dict:
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


_cache: dict = _load_cache()


def _cache_set(company: str, entry: dict) -> None:
    with _cache_lock:
        _cache[company] = entry


def _save_cache() -> None:
    tmp = CACHE_FILE + ".tmp"
    try:
        with _cache_lock:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(_cache, f, ensure_ascii=False)
            os.replace(tmp, CACHE_FILE)
    except OSError:
        pass


# ============================================================
# 7. FETCH RSS
# ============================================================

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})


def get_company_news(company: str) -> list[dict]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(company)}+when:3d&hl=en-IN&gl=IN&ceid=IN:en"
    )

    # feedparser.parse(url) has no timeout; fetch with requests instead.
    resp = session.get(url, timeout=FETCH_TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    articles = []
    for entry in feed.entries[:RSS_LIMIT]:
        title = entry.get("title", "").strip()
        if not title:
            continue

        parsed = entry.get("published_parsed")
        articles.append(
            {
                "title": title,
                "published_date": entry.get("published", "").strip(),
                "ts": timegm(parsed) if parsed else 0,
            }
        )
    return articles


# ============================================================
# 8. FILTER + DEDUPE
# ============================================================

# Word-boundary matching (the old substring check matched "ai" inside
# "said", "pay" inside "company", etc., so nearly everything passed).
RELEVANCE_KEYWORDS = [
    "hire", "hiring", "recruit", "recruitment", "job", "workforce",
    "intern", "internship", "fresher", "graduate", "campus",
    "layoff", "laid off", "job cuts", "workforce reduction", "hiring freeze",
    "salary", "salaries", "pay", "compensation", "appraisal", "raise",
    "office", "expansion", "india", "new location",
    "ceo", "cto", "chief", "executive", "leadership",
    "funding", "investment", "growth", "deal", "business", "revenue",
    "ai", "artificial intelligence", "technology", "tech", "product", "launch",
    "acquire", "acquisition", "merger", "merge", "restructuring",
    "return to office", "remote work", "workplace", "employee",
]

RELEVANCE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in RELEVANCE_KEYWORDS) + r")(?:s|d|ed|ing)?\b",
    re.IGNORECASE,
)

_SOURCE_SUFFIX = re.compile(r"\s+-\s+[^-]{2,40}$")   # "... - Reuters"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title(title: str) -> str:
    title = _SOURCE_SUFFIX.sub("", title)
    return _NON_ALNUM.sub(" ", title.lower()).strip()


def prepare_articles(articles: list[dict]) -> list[dict]:
    # Newest first, so the cap below keeps the freshest articles.
    articles = sorted(articles, key=lambda a: a["ts"], reverse=True)

    seen = set()
    selected = []

    for article in articles:
        key = normalize_title(article["title"])
        if key in seen:
            continue
        seen.add(key)

        if RELEVANCE_RE.search(article["title"]):
            selected.append(article)

        if len(selected) >= MAX_ARTICLES_TO_LLM:
            break

    return selected


def format_news(articles: list[dict]) -> str:
    return "\n".join(
        f"Article {i}\nTitle: {a['title']}\nPublished: {a['published_date']}\n"
        for i, a in enumerate(articles, start=1)
    )


# ============================================================
# 9. PROCESS ONE COMPANY
# ============================================================

def process_company(company: str, refresh: bool = False) -> dict:
    start = time.perf_counter()
    now = time.time()
    cached = _cache.get(company)

    # 1) Fresh cache -> no network, no LLM.
    if cached and not refresh and now - cached["ts"] < CACHE_TTL_SECONDS:
        print(f"✓ {company:<12} cache hit")
        return cached["data"]

    try:
        articles = prepare_articles(get_company_news(company))

        # 2) Nothing relevant -> no LLM call.
        if not articles:
            data = {"company": company, "news": []}
            _cache_set(company, {"ts": now, "fp": "", "data": data})
            print(f"✓ {company:<12} no relevant news")
            return data

        news_text = format_news(articles)
        fingerprint = hashlib.sha1(news_text.encode("utf-8")).hexdigest()

        # 3) Same articles as last time -> reuse the previous LLM result.
        if cached and cached.get("fp") == fingerprint:
            _cache_set(company, {**cached, "ts": now})
            print(f"✓ {company:<12} unchanged, LLM skipped")
            return cached["data"]

        # 4) New articles -> one LLM call.
        messages = prompt.format_messages(company=company, news=news_text)

        with LLM_SEMAPHORE:
            result = structured_model.invoke(messages)

        if result is None:
            raise ValueError("model returned no structured output")

        data = result.model_dump()
        data["company"] = company

        _cache_set(company, {"ts": now, "fp": fingerprint, "data": data})

        print(
            f"✓ {company:<12} {len(data['news'])} news "
            f"({time.perf_counter() - start:.2f}s)"
        )
        return data

    except Exception as e:
        print(f"✗ {company}: {e}")

        # Serve the last good result instead of an empty one.
        if cached:
            return {**cached["data"], "stale": True}

        return {"company": company, "news": [], "error": str(e)}


# ============================================================
# 10. PIPELINE
# ============================================================

def run_pipeline(refresh: bool = False) -> list[dict]:
    start = time.perf_counter()

    # process_company never raises, and map() keeps company order.
    with ThreadPoolExecutor(max_workers=len(TARGET_COMPANIES)) as executor:
        results = list(
            executor.map(lambda c: process_company(c, refresh), TARGET_COMPANIES)
        )

    _save_cache()

    print(f"Completed in {time.perf_counter() - start:.2f} seconds")
    return results


async def run_pipeline_async(refresh: bool = False) -> list[dict]:
    """Use this inside FastAPI: results = await run_pipeline_async()"""
    return await asyncio.to_thread(run_pipeline, refresh)


# ============================================================
# 11. TEST
# ============================================================

# if __name__ == "__main__":
#     # python news_pipeline_final.py          -> uses cache when fresh
#     # python news_pipeline_final.py --fresh  -> forces a refetch
#     for item in run_pipeline(refresh="--fresh" in sys.argv):
#         print("\n", item)