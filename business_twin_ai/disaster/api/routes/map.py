"""Disaster map warning state API route (spec §10 / §14)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.disaster.engines.warning_state import MapWarningStateUpdater
from business_twin_ai.disaster.models import IncidentCluster
from business_twin_ai.disaster.schemas.schemas import MapWarningOut, MapWarningResponse

router = APIRouter()


@router.get("/map/warnings", response_model=MapWarningResponse)
async def get_map_warnings(db: AsyncSession = Depends(get_db)) -> MapWarningResponse:
    """Return the current warning level per cluster + a level summary."""
    updater = MapWarningStateUpdater()
    result = await db.execute(
        select(IncidentCluster).order_by(IncidentCluster.last_update.desc()).limit(500)
    )
    clusters = list(result.scalars().all())

    warnings = []
    summary = {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0}
    for cluster in clusters:
        level = updater.compute_warning_level(
            cluster.average_severity, cluster.report_count
        )
        summary[level] = summary.get(level, 0) + 1
        warnings.append(
            MapWarningOut(
                cluster_id=cluster.cluster_id,
                disaster_type=cluster.disaster_type,
                warning_level=level,
                active_reports=cluster.report_count,
                cluster_size=cluster.report_count,
                average_severity=cluster.average_severity,
                center_latitude=cluster.center_latitude,
                center_longitude=cluster.center_longitude,
                last_update=cluster.last_update,
            )
        )

    return MapWarningResponse(
        generated_at=datetime.now(timezone.utc),
        warnings=warnings,
        summary=summary,
    )
