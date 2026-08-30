"""API routes for Digital Twin management."""

from __future__ import annotations

import json
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.core.engines.digital_twin import DigitalTwinEngine
from business_twin_ai.core.engines.source_checklist import SourceChecklistEngine
from business_twin_ai.core.schemas.schemas import (
    BusinessData,
    ChecklistAuditSummary,
    ChecklistOverviewResponse,
    ChecklistSaveRequest,
    DigitalTwinResponse,
    SourceChecklistResponse,
)
from business_twin_ai.database import get_db

router = APIRouter(prefix="/digital-twins", tags=["Digital Twin"])


@router.post("", response_model=DigitalTwinResponse, status_code=201)
async def create_twin(data: BusinessData, db: AsyncSession = Depends(get_db)) -> DigitalTwinResponse:
    """Create a new digital twin from structured business data."""
    engine = DigitalTwinEngine(db)
    twin = await engine.create_twin(data)
    return DigitalTwinResponse.model_validate(twin)


@router.get("", response_model=List[DigitalTwinResponse])
async def list_twins(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> List[DigitalTwinResponse]:
    """List all digital twins."""
    engine = DigitalTwinEngine(db)
    twins = await engine.list_twins(limit=limit, offset=offset)
    return [DigitalTwinResponse.model_validate(t) for t in twins]


@router.get("/sources/overview", response_model=ChecklistOverviewResponse)
async def sources_overview(
    db: AsyncSession = Depends(get_db),
) -> ChecklistOverviewResponse:
    """Per-profile coverage overview across every digital twin.

    One summary row per business profile: coverage %, completed sections, and
    status counts, plus a ``regressed`` flag when coverage dropped below the
    last scheduled audit snapshot.
    """
    from datetime import datetime, timezone

    engine = SourceChecklistEngine(db)
    items = await engine.build_overview()
    return ChecklistOverviewResponse(
        generated_at=datetime.now(timezone.utc), items=items
    )


@router.post("/sources/refresh", response_model=ChecklistAuditSummary)
async def refresh_sources(
    db: AsyncSession = Depends(get_db),
) -> ChecklistAuditSummary:
    """Re-audit every profile's source checklist now.

    Refreshes the audit snapshots and reports any coverage / verified-section
    regressions. The same routine runs automatically on a schedule.
    """
    engine = SourceChecklistEngine(db)
    summary = await engine.audit_all()
    return ChecklistAuditSummary(**summary)


@router.get("/{twin_id}/sources", response_model=SourceChecklistResponse)
async def get_twin_sources(
    twin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SourceChecklistResponse:
    """Get the data-source checklist for a digital twin (business profile).

    Audits every source feeding the profile — user-provided data, derived AI
    artifacts, and the real-time market feed — with status, coverage,
    freshness, owner, and saved completion state for each section.
    """
    engine = SourceChecklistEngine(db)
    checklist = await engine.build_checklist(twin_id)
    if checklist is None:
        raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
    return checklist


@router.put("/{twin_id}/sources", response_model=SourceChecklistResponse)
async def save_twin_sources(
    twin_id: uuid.UUID,
    request: ChecklistSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> SourceChecklistResponse:
    """Persist the saved completion state of a profile's source checklist.

    The body is a map of ``source_id → completed``. The saved state survives
    across sessions and is merged into every later GET.
    """
    engine = SourceChecklistEngine(db)
    checklist = await engine.save_completions(twin_id, request.completions)
    if checklist is None:
        raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
    return checklist


@router.get("/{twin_id}/sources/export")
async def export_twin_sources(
    twin_id: uuid.UUID,
    format: str = "markdown",
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export a project-specific report for a business profile.

    ``format`` is one of ``markdown``, ``json``, ``csv``, ``html``, ``pdf``.
    The report reuses the existing captured profile fields, the source-check
    statuses, stored recommendations (strategies), and checklist notes.
    Returns a downloadable file.
    """
    engine = SourceChecklistEngine(db)
    fmt = format.lower()

    if fmt == "json":
        checklist = await engine.build_checklist(twin_id)
        if checklist is None:
            raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
        from fastapi.encoders import jsonable_encoder

        content = json.dumps(jsonable_encoder(checklist.model_dump()), indent=2, default=str)
        media_type, ext, company = "application/json", "json", checklist.company
    else:
        report = await engine.build_report(twin_id)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
        company = report["company"]
        if fmt == "markdown":
            content, media_type, ext = engine.export_markdown(report), "text/markdown", "md"
        elif fmt == "csv":
            content, media_type, ext = engine.export_csv(report), "text/csv", "csv"
        elif fmt == "html":
            content, media_type, ext = engine.export_html(report), "text/html", "html"
        elif fmt == "pdf":
            try:
                pdf_bytes = engine.export_pdf(report)
            except ImportError as exc:
                raise HTTPException(
                    status_code=501, detail="PDF generation unavailable (reportlab missing)"
                ) from exc
            company_slug = _company_slug(company)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="{company_slug}-profile-report.pdf"'
                    )
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="format must be one of: markdown, json, csv, html, pdf",
            )

    company_slug = _company_slug(company)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{company_slug}-profile-report.{ext}"'
            )
        },
    )


def _company_slug(company: str) -> str:
    """Build a filesystem-safe slug from a company name."""
    return (
        company.lower()
        .replace(" ", "-")
        .replace('"', "")
        .replace("'", "")
        .replace("/", "-")
    )


@router.get("/{twin_id}", response_model=DigitalTwinResponse)
async def get_twin(twin_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> DigitalTwinResponse:
    """Get a digital twin by ID."""
    engine = DigitalTwinEngine(db)
    twin = await engine.get_twin(twin_id)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
    return DigitalTwinResponse.model_validate(twin)


@router.put("/{twin_id}", response_model=DigitalTwinResponse)
async def update_twin(
    twin_id: uuid.UUID,
    data: BusinessData,
    db: AsyncSession = Depends(get_db),
) -> DigitalTwinResponse:
    """Update an existing digital twin with new business data."""
    engine = DigitalTwinEngine(db)
    twin = await engine.update_twin(twin_id, data)
    if not twin:
        raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
    return DigitalTwinResponse.model_validate(twin)


@router.delete("/{twin_id}", status_code=204)
async def delete_twin(twin_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    """Delete a digital twin and all associated data."""
    engine = DigitalTwinEngine(db)
    deleted = await engine.delete_twin(twin_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Digital twin {twin_id} not found")
