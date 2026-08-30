"""Incident clustering engine (spec §5)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config
from business_twin_ai.disaster.models import IncidentCluster
from business_twin_ai.disaster.utils.geo import bounding_box, haversine_km

logger = logging.getLogger("business_twin_ai.disaster.validation")


class ClusteringService:
    """Assigns each report to a cluster using GPS radius + time window + type.

    Clusters are created lazily: when a report does not fit any existing
    cluster, a new one is created. Cluster centers and averages are updated
    incrementally so the cost stays O(1) per report.
    """

    def __init__(
        self,
        db: AsyncSession,
        config: ValidationConfig = default_config,
    ) -> None:
        self.db = db
        self.config = config

    async def _next_cluster_number(self) -> int:
        """Find the next free cluster sequence number.

        Note: this is a heuristic (max+1 scan). Under heavy concurrency two
        requests may pick the same number; the caller retries on the unique
        constraint violation with a fresh UUID-based id (see ``assign``).
        """
        result = await self.db.execute(select(IncidentCluster.cluster_id))
        numbers = []
        for (cid,) in result.all():
            suffix = cid.rsplit("_", 1)[-1]
            if suffix.isdigit():
                numbers.append(int(suffix))
        return max(numbers, default=0) + 1

    async def assign(
        self,
        *,
        latitude: float,
        longitude: float,
        disaster_type: str,
        severity: float,
        timestamp: datetime,
        preferred_cluster_id: Optional[str] = None,
    ) -> IncidentCluster:
        """Assign a report to a cluster, creating/updating it.

        ``preferred_cluster_id`` is used when duplicate detection already found
        the report's parent cluster — we join that one directly.
        """
        ts = timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if preferred_cluster_id:
            existing = await self.db.execute(
                select(IncidentCluster).where(IncidentCluster.cluster_id == preferred_cluster_id)
            )
            cluster = existing.scalar_one_or_none()
            if cluster is not None:
                return await self._add_report(cluster, latitude, longitude, severity, ts)

        # Spatial + temporal + type pre-filter.
        min_lat, max_lat, min_lon, max_lon = bounding_box(
            latitude, longitude, self.config.CLUSTER_RADIUS_KM
        )
        window_start = ts - timedelta(hours=self.config.CLUSTER_TIME_WINDOW_HOURS)

        result = await self.db.execute(
            select(IncidentCluster)
            .where(
                IncidentCluster.disaster_type == disaster_type,
                IncidentCluster.last_update >= window_start,
                IncidentCluster.center_latitude >= min_lat,
                IncidentCluster.center_latitude <= max_lat,
                IncidentCluster.center_longitude >= min_lon,
                IncidentCluster.center_longitude <= max_lon,
            )
            .order_by(IncidentCluster.last_update.desc())
            .limit(self.config.CLUSTER_MAX_QUERY)
        )
        candidates = result.scalars().all()

        best: Optional[IncidentCluster] = None
        best_dist = float("inf")
        for cand in candidates:
            dist = haversine_km(latitude, longitude, cand.center_latitude, cand.center_longitude)
            if dist <= self.config.CLUSTER_RADIUS_KM and dist < best_dist:
                best = cand
                best_dist = dist

        if best is not None:
            return await self._add_report(best, latitude, longitude, severity, ts)

        # No fit → new cluster. Try the sequential id first; if another request
        # won the race (unique constraint), fall back to a UUID-based id so the
        # write never fails under concurrency.
        number = await self._next_cluster_number()
        try:
            cluster = await self._insert_cluster(
                f"{self.config.CLUSTER_ID_PREFIX}{number}",
                disaster_type, latitude, longitude, severity, ts,
            )
        except IntegrityError:
            await self.db.rollback()
            cluster = await self._insert_cluster(
                f"{self.config.CLUSTER_ID_PREFIX}{uuid.uuid4().hex[:8]}",
                disaster_type, latitude, longitude, severity, ts,
            )
        logger.info("[clustering] created %s (type=%s)", cluster.cluster_id, disaster_type)
        return cluster

    async def _insert_cluster(
        self,
        cluster_id: str,
        disaster_type: str,
        latitude: float,
        longitude: float,
        severity: float,
        timestamp: datetime,
    ) -> IncidentCluster:
        cluster = IncidentCluster(
            cluster_id=cluster_id,
            disaster_type=disaster_type,
            center_latitude=latitude,
            center_longitude=longitude,
            report_count=1,
            average_severity=severity,
            last_update=timestamp,
            warning_level="GREEN",
        )
        self.db.add(cluster)
        await self.db.flush()
        return cluster

    async def _add_report(
        self,
        cluster: IncidentCluster,
        latitude: float,
        longitude: float,
        severity: float,
        timestamp: datetime,
    ) -> IncidentCluster:
        """Incrementally fold a report into an existing cluster."""
        old_count = cluster.report_count
        new_count = old_count + 1
        cluster.center_latitude = (cluster.center_latitude * old_count + latitude) / new_count
        cluster.center_longitude = (cluster.center_longitude * old_count + longitude) / new_count
        cluster.average_severity = (cluster.average_severity * old_count + severity) / new_count
        cluster.report_count = new_count
        cluster.last_update = timestamp
        await self.db.flush()
        logger.info(
            "[clustering] %s += report (count=%d avg_severity=%.2f)",
            cluster.cluster_id,
            new_count,
            cluster.average_severity,
        )
        return cluster
