"""API routes for real-time market news (GDELT-backed)."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from business_twin_ai.core.schemas.schemas import NewsItem
from business_twin_ai.services.news.gdelt import fetch_market_news

router = APIRouter(prefix="/news", tags=["News"])


@router.get("", response_model=List[NewsItem])
async def get_market_news(
    q: str = Query(..., min_length=2, max_length=300, description="Topic / company / region query"),
    limit: int = Query(8, ge=1, le=25),
) -> List[NewsItem]:
    """Fetch the latest news headlines for a query (GDELT DOC API).

    Falls back to a curated headline pool when the GDELT service is
    unreachable, so the endpoint always returns useful content.
    """
    articles = await fetch_market_news(q, limit=limit)
    return [NewsItem(**a) for a in articles]
