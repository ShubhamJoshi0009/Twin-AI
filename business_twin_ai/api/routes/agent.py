"""API routes for Business Decision Agent (LLM Q&A)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.agent import AgentEngine
from business_twin_ai.core.schemas.schemas import AgentQuery, AgentResponse
from business_twin_ai.database import get_db

router = APIRouter(prefix="/agent", tags=["Business Agent"])


@router.post("/{twin_id}/ask", response_model=AgentResponse)
async def ask_agent(
    twin_id: uuid.UUID,
    query: AgentQuery,
    db: AsyncSession = Depends(get_db),
) -> AgentResponse:
    """Ask the Business Agent a natural language question."""
    engine = AgentEngine(db)
    try:
        response = await engine.ask(twin_id, query.question)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return response
