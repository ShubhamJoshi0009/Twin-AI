"""Incident cluster API routes (spec §14)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.disaster.models import DisasterReport, IncidentCluster
from business_twin_ai.disaster.schemas.schemas import DisasterReportOut, IncidentClusterOut

router = APIRouter()


@router.get("/clusters", response_model=list[IncidentClusterOut])
async def list_clusters(db: AsyncSession = Depends(get_db)) -> list[IncidentCluster]:
    """List all incident clusters with their warning state."""
    result = await db.execute(
        select(IncidentCluster).order_by(IncidentCluster.last_update.desc()).limit(500)
    )
    return list(result.scalars().all())


@router.get("/clusters/{cluster_id}", response_model=dict)
async def get_cluster(
    cluster_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return one cluster plus the reports that belong to it."""
    result = await db.execute(
        select(IncidentCluster).where(IncidentCluster.cluster_id == cluster_id)
    )
    cluster = result.scalar_one_or_none()
    if cluster is None:
        raise HTTPException(status_code=404, detail="Cluster not found")

    reports_result = await db.execute(
        select(DisasterReport)
        .where(DisasterReport.cluster_id == cluster_id)
        .order_by(DisasterReport.timestamp.desc())
        .limit(200)
    )
    reports = list(reports_result.scalars().all())
    return {
        "cluster": IncidentClusterOut.model_validate(cluster),
        "reports": [DisasterReportOut.model_validate(r) for r in reports],
    }
