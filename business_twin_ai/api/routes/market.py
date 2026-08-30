"""API routes for the Market Watch dashboard."""

from __future__ import annotations

from fastapi import APIRouter

from business_twin_ai.agentic.market import get_market_watch
from business_twin_ai.core.schemas.schemas import MarketWatchResponse

router = APIRouter(prefix="/market", tags=["Market Watch"])


@router.get("/watch", response_model=MarketWatchResponse)
async def market_watch(news_limit: int = 3) -> MarketWatchResponse:
    """Live market watch: commodities, freight and geopolitical drivers with news + impact scores."""
    news_limit = max(1, min(news_limit, 8))
    return await get_market_watch(news_limit=news_limit)
