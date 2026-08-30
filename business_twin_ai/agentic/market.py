"""Market Watch service — commodity / freight / geopolitical watchlist with live news.

Each watch item tracks a market driver relevant to a trader or business owner,
pulls the latest GDELT news for it, and scores the likely impact on the
business (0–100) based on sentiment and headline keywords.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from business_twin_ai.core.schemas.schemas import MarketWatchResponse, NewsItem, WatchItem
from business_twin_ai.services.news.gdelt import fetch_market_news

logger = logging.getLogger(__name__)

# Default watchlist — broad enough to be relevant to any business/trader.
DEFAULT_WATCHLIST: List[Dict[str, Any]] = [
    {"id": "crude-oil", "name": "Crude Oil (Brent)", "category": "commodity", "query": "crude oil Brent price", "base_impact": 45},
    {"id": "freight-rates", "name": "Container Freight Rates", "category": "freight", "query": "container shipping freight rates", "base_impact": 55},
    {"id": "red-sea", "name": "Red Sea / Suez Shipping", "category": "geopolitical", "query": "Red Sea shipping Suez disruption", "base_impact": 65},
    {"id": "panama-canal", "name": "Panama Canal Transits", "category": "geopolitical", "query": "Panama Canal drought transit", "base_impact": 50},
    {"id": "copper", "name": "Copper", "category": "commodity", "query": "copper price", "base_impact": 35},
    {"id": "wheat", "name": "Wheat", "category": "commodity", "query": "wheat price supply", "base_impact": 40},
    {"id": "semiconductors", "name": "Semiconductors", "category": "index", "query": "semiconductor chip demand supply", "base_impact": 45},
    {"id": "tariffs", "name": "Global Trade / Tariffs", "category": "geopolitical", "query": "trade tariffs import export", "base_impact": 55},
]

_NEG = ["disrupt", "block", "war", "tension", "shortage", "crisis", "delay", "risk", "drought", "sanction", "tariff", "surge", "collapse", "crash", "halt", "attack"]
_POS = ["growth", "recover", "record", "boost", "gain", "rise", "strong", "stabiliz", "expans", "surplus", "rebound"]


def _score_news(items: List[Dict[str, Any]], base_impact: int) -> tuple:
    """Return (impact_score, sentiment, direction) from news headlines."""
    titles = [n.get("title", "") for n in items]
    score = 0
    for t in titles:
        t_lower = t.lower()
        score += sum(1 for w in _NEG if w in t_lower)
        score -= sum(1 for w in _POS if w in t_lower)
    if score >= 3:
        sentiment, direction = "negative", "negative"
    elif score >= 1:
        sentiment, direction = "mixed", "negative"
    elif score <= -2:
        sentiment, direction = "positive", "positive"
    else:
        sentiment, direction = "neutral", "neutral"

    impact = max(5, min(95, base_impact + score * 8))
    trend = "volatile" if abs(score) >= 3 else ("up" if score <= -1 else ("down" if score >= 1 else "stable"))
    return impact, sentiment, direction, trend


async def _build_watch_item(item: Dict[str, Any], limit: int) -> WatchItem:
    articles = await fetch_market_news(item["query"], limit=limit)
    impact, sentiment, direction, trend = _score_news(articles, item["base_impact"])
    news = [
        NewsItem(**{k: a[k] for k in ("title", "url", "source", "published_at", "language", "country") if k in a})
        for a in articles
    ]
    rationale = (
        f"{len(articles)} headline(s) for \"{item['name']}\". "
        f"Net sentiment {sentiment}; estimated impact {impact}/100 on operations."
    )
    return WatchItem(
        id=item["id"],
        name=item["name"],
        category=item["category"],
        trend=trend,
        sentiment=sentiment,
        impact_score=impact,
        direction=direction,
        rationale=rationale,
        news=news,
    )


async def get_market_watch(
    watchlist: Optional[List[Dict[str, Any]]] = None,
    news_limit: int = 3,
) -> MarketWatchResponse:
    """Build the market watch dashboard with live news per item.

    Items are fetched concurrently — the news service caches per-query, so
    repeated loads are near-instant and a single first load completes in one
    upstream timeout instead of one per item.
    """

    watchlist = watchlist or DEFAULT_WATCHLIST
    items = await _build_watch_item_safe(watchlist, news_limit)

    # Overall market context from the aggregate.
    neg_count = sum(1 for i in items if i.sentiment == "negative")
    positive_count = sum(1 for i in items if i.sentiment == "positive")
    if neg_count >= 3:
        context = "Broadly risk-off: several watch items show negative news momentum."
    elif positive_count >= 3:
        context = "Supportive backdrop: most watch items are trending positive."
    else:
        context = "Mixed signals across commodities, freight and geopolitics."

    return MarketWatchResponse(
        mode="live" if any(i.news for i in items) else "curated",
        market_context=context,
        items=items,
        updated_at=datetime.now(timezone.utc),
    )


async def _build_watch_item_safe(watchlist: List[Dict[str, Any]], limit: int) -> List[WatchItem]:
    """Build watch items concurrently, degrading per-item on failure."""
    import asyncio

    async def one(item: Dict[str, Any]) -> WatchItem:
        try:
            return await _build_watch_item(item, limit)
        except Exception as exc:  # noqa: BLE001 — never kill the whole dashboard
            logger.info("Market watch item %s failed (%s) — curated fallback", item["id"], exc)
            return await _curated_watch_item(item)

    return list(await asyncio.gather(*(one(item) for item in watchlist)))


async def _curated_watch_item(item: Dict[str, Any]) -> WatchItem:
    """Fallback item with no live news (offline safe)."""
    return WatchItem(
        id=item["id"],
        name=item["name"],
        category=item["category"],
        trend="stable",
        sentiment="neutral",
        impact_score=item["base_impact"],
        direction="neutral",
        rationale=f"Live news unavailable — baseline impact {item['base_impact']}/100.",
        news=[],
    )
