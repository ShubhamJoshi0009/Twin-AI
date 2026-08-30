"""Keyed news provider backed by NewsAPI.org (https://newsapi.org).

Used ahead of the free GDELT feed whenever ``NEWS_API_KEY`` is configured:
headline lookups prefer NewsAPI.org (broader coverage, fresher headlines)
and transparently fall back to GDELT → curated pool on failure / rate-limit.

Normalizes NewsAPI's article shape into the same dicts the rest of the app
consumes: title, url, source, published_at, language, country.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import httpx

from business_twin_ai.config import settings

logger = logging.getLogger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWSAPI_TIMEOUT_SECONDS = 3.0
NEWSAPI_CONNECT_TIMEOUT_SECONDS = 1.5

# In-process TTL cache (NewsAPI free tier is 100 req/day — cache aggressively).
_CACHE_TTL_SECONDS = 10 * 60
_cache: Dict[tuple, tuple] = {}  # (query, limit) -> (expires_at, articles)

# Negative cache: failures (timeout, rate limit, bad key) are remembered for a
# short TTL so a broken/expired key doesn't stall every news call behind a
# wasted round-trip. After a definitive `apiKeyInvalid`/`rateLimited`, we
# short-circuit for the process lifetime and let the GDELT chain take over.
_NEG_CACHE_TTL_SECONDS = 60
_neg_cache: Dict[tuple, tuple] = {}  # (query, limit) -> (expires_at, None)
_KEY_REJECTED = False  # process-lifetime: NewsAPI rejected our key — stop trying


def _normalize(articles: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """Map NewsAPI article objects to the app's normalized news shape."""
    out: List[Dict[str, Any]] = []
    for a in (articles or [])[:limit]:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        published = a.get("publishedAt")
        if published and published.endswith("Z"):
            published = published.replace("Z", "+00:00")
        out.append({
            "title": title,
            "url": a.get("url") or "",
            "source": (a.get("source") or {}).get("name") or "NewsAPI",
            "published_at": published,
            "language": "eng",
            "country": a.get("country") or "",
        })
    return out


async def fetch_newsapi_news(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Fetch recent headlines for ``query`` from NewsAPI.org.

    Returns [] on any failure (bad key, rate limit, timeout, empty results) —
    callers fall back to GDELT / curated pool, so this never blocks the UI.
    """
    global _KEY_REJECTED
    if not settings.NEWS_API_KEY or _KEY_REJECTED:
        return []

    limit = max(1, min(int(limit), 25))
    key = (query[:120], limit)
    import time as _time

    now = _time.monotonic()
    hit = _cache.get(key)
    if hit and hit[0] > now:
        return list(hit[1])
    neg = _neg_cache.get(key)
    if neg and neg[0] > now:
        return []

    params = {
        "q": query[:300],
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": str(limit),
        "apiKey": settings.NEWS_API_KEY,
        # Developer plan searches back ~a month; clamp to 7 days to stay fresh.
        "from": (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat(),
    }
    articles: List[Dict[str, Any]] = []
    rejected = False
    try:
        timeout = httpx.Timeout(
            NEWSAPI_TIMEOUT_SECONDS,
            connect=NEWSAPI_CONNECT_TIMEOUT_SECONDS,
            pool=NEWSAPI_CONNECT_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(NEWSAPI_URL, params=params)
            data = resp.json()
            code = (data or {}).get("code") or ""
            if data.get("status") == "ok":
                articles = _normalize(data.get("articles") or [], limit)
            elif code in ("apiKeyInvalid", "apiKeyDisabled", "rateLimited", "maximumResultsReached"):
                rejected = True
                logger.info("NewsAPI %s — disabling keyed provider", code)
            else:
                logger.info("NewsAPI status=%s for query %r — falling back", data.get("status"), query)
        if not articles and not rejected:
            logger.info("NewsAPI returned no articles for query %r — falling back", query)
    except Exception as exc:  # noqa: BLE001 — never fail the caller
        logger.info("NewsAPI unavailable for %r (%s) — falling back", query, exc)

    if rejected:
        _KEY_REJECTED = True  # stop wasting round-trips for the process lifetime
        return []
    if not articles:
        _neg_cache[key] = (now + _NEG_CACHE_TTL_SECONDS, None)  # short negative cache
        return []

    _cache[key] = (now + _CACHE_TTL_SECONDS, articles)
    return list(articles)
