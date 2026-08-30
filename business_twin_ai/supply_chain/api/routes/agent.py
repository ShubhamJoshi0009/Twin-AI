"""Supply Chain Agent API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.supply_chain.engines.agent import SupplyChainAgentEngine
from business_twin_ai.supply_chain.schemas.schemas import SupplyChainAgentResponse, SupplyChainQuery

router = APIRouter()


@router.post("/ask", response_model=SupplyChainAgentResponse)
async def ask_agent(query: SupplyChainQuery, db: AsyncSession = Depends(get_db)):
    """Ask the Supply Chain AI agent a question."""
    engine = SupplyChainAgentEngine(db)
    return await engine.ask(query.question)
