"""API routes for the Agentic AI layer — multi-agent orchestration and briefing."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.agentic.agents import AgenticOrchestrator
from business_twin_ai.agentic.briefing import BriefingGenerator
from business_twin_ai.core.schemas.schemas import (
    AgentQuery,
    BriefingResponse,
    OrchestrationResponse,
)
from business_twin_ai.database import get_db

router = APIRouter(prefix="/agentic", tags=["Agentic AI"])


@router.post("/{twin_id}/orchestrate", response_model=OrchestrationResponse)
async def orchestrate(
    twin_id: uuid.UUID,
    query: AgentQuery,
    db: AsyncSession = Depends(get_db),
) -> OrchestrationResponse:
    """Run the full multi-agent pipeline (financial, market, supply chain, strategy)."""
    orchestrator = AgenticOrchestrator(db, twin_id)
    try:
        result, _ = await orchestrator.orchestrate(question=query.question)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return OrchestrationResponse(**result)


@router.post("/{twin_id}/briefing", response_model=BriefingResponse)
async def generate_briefing(
    twin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BriefingResponse:
    """Generate a one-shot executive briefing for the twin."""
    generator = BriefingGenerator(db)
    try:
        return await generator.generate(twin_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
