"""Duplicate detection stage (spec §4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.models import DisasterReport
from business_twin_ai.disaster.utils.geo import bounding_box, haversine_km
from business_twin_ai.disaster.utils.text import text_similarity, truncate
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin


@dataclass
class DuplicateResult:
    """Result of duplicate detection."""

    duplicate: bool = False
    duplicate_score: float = 0.0
    duplicate_of: Optional[str] = None
    candidates_checked: int = 0
    reasons: List[str] = field(default_factory=list)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class DuplicateDetectionStage(TimedStageMixin):
    """Compare the incoming report against recent stored reports.

    Similarity is a weighted blend of GPS proximity, time proximity, image hash
    equality, text similarity, disaster type and severity (spec §4). Scores run
    0-100; > ``DUPLICATE_THRESHOLD`` marks the report as a duplicate.
    """

    name = "duplicate"

    async def run(self, context: StageContext) -> DuplicateResult:
        cfg: ValidationConfig = context.config
        payload = context.payload

        if context.db is None:
            return DuplicateResult(reasons=["no database available for comparison"])

        lat = payload.get("latitude")
        lon = payload.get("longitude")
        if lat is None or lon is None:
            return DuplicateResult(reasons=["missing coordinates, cannot compare"])

        ts = payload.get("timestamp")
        ts = _as_utc(ts) if isinstance(ts, datetime) else datetime.now(timezone.utc)
        window_start = ts - timedelta(hours=cfg.DUP_TIME_WINDOW_HOURS)
        window_end = ts + timedelta(hours=cfg.DUP_TIME_WINDOW_HOURS)

        # Spatial pre-filter: bounding box around the report (fast, indexable).
        min_lat, max_lat, min_lon, max_lon = bounding_box(
            lat, lon, cfg.CLUSTER_RADIUS_KM
        )

        # Guard against unbounded scans: only the most recent candidates matter.
        query = (
            select(*[getattr(DisasterReport, c) for c in cfg.duplicate_candidate_columns])
            .where(
                DisasterReport.timestamp >= window_start,
                DisasterReport.timestamp <= window_end,
                DisasterReport.latitude >= min_lat,
                DisasterReport.latitude <= max_lat,
                DisasterReport.longitude >= min_lon,
                DisasterReport.longitude <= max_lon,
            )
            .order_by(DisasterReport.timestamp.desc())
            .limit(cfg.DUP_QUERY_LIMIT)
        )
        rows = (await context.db.execute(query)).mappings().all()
        if not rows:
            return DuplicateResult(candidates_checked=0)

        best_score = 0.0
        best_id: Optional[str] = None
        for row in rows:
            score = self._similarity(payload, row, cfg)
            if score > best_score:
                best_score = score
                best_id = str(row["id"])

        duplicate = best_score > cfg.DUPLICATE_THRESHOLD
        return DuplicateResult(
            duplicate=duplicate,
            duplicate_score=round(best_score, 2),
            duplicate_of=best_id if duplicate else None,
            candidates_checked=len(rows),
            reasons=(
                [f"duplicate of report {best_id} (score {best_score:.1f})"]
                if duplicate
                else []
            ),
        )

    def _similarity(self, payload: dict, row: dict, cfg: ValidationConfig) -> float:
        """Weighted similarity (0-100) between payload and a candidate row.

        Weights are renormalised so that components which cannot be evaluated
        (e.g. image hash when neither report has an image) do not drag the
        score down — an otherwise identical pair can still reach ~100.
        """
        lat, lon = payload["latitude"], payload["longitude"]

        # ── Location proximity (0..1) ──
        dist_km = haversine_km(lat, lon, row["latitude"], row["longitude"])
        loc_sim = max(0.0, 1.0 - dist_km / cfg.DUP_NEARBY_RADIUS_KM)

        # ── Time proximity (0..1) ──
        ts = payload.get("timestamp")
        ts = _as_utc(ts) if isinstance(ts, datetime) else datetime.now(timezone.utc)
        hours = abs((ts - _as_utc(row["timestamp"])).total_seconds()) / 3600.0
        time_sim = max(0.0, 1.0 - hours / cfg.DUP_TIME_WINDOW_HOURS)

        # ── Image hash equality (0..1) ──
        payload_hash = payload.get("_image_hash")
        row_hash = row.get("image_hash")
        both_images = bool(payload_hash) and bool(row_hash)
        one_image = bool(payload_hash) != bool(row_hash)
        if both_images:
            image_sim = 1.0 if payload_hash == row_hash else 0.0
        elif one_image:
            image_sim = 0.5  # one side lacks an image — partial credit
        else:
            image_sim = 0.0

        # ── Text similarity (0..1) ──
        my_text = truncate(
            f"{payload.get('title', '')} {payload.get('description', '')}",
            cfg.DUP_MAX_TEXT_LENGTH,
        )
        row_text = truncate(
            f"{row.get('title', '')} {row.get('description', '')}",
            cfg.DUP_MAX_TEXT_LENGTH,
        )
        text_sim = text_similarity(my_text, row_text)

        # ── Disaster type (0..1) ──
        type_sim = 1.0 if str(payload.get("disaster_type", "")).lower() == str(
            row.get("disaster_type", "")
        ).lower() else 0.0

        # ── Severity closeness (0..1) ──
        sev_diff = abs(float(payload.get("severity", 0.0)) - float(row.get("severity", 0.0)))
        sev_sim = max(0.0, 1.0 - sev_diff / 10.0)

        # ── Weighted blend with renormalisation over applicable components ──
        # The image component is dropped entirely when neither report has one;
        # otherwise the maximum possible score would stay below the threshold.
        components = {
            "location": (cfg.DUP_W_LOCATION, loc_sim),
            "time": (cfg.DUP_W_TIME, time_sim),
            "text": (cfg.DUP_W_TEXT, text_sim),
            "type": (cfg.DUP_W_TYPE, type_sim),
            "severity": (cfg.DUP_W_SEVERITY, sev_sim),
        }
        if both_images or one_image:
            components["image"] = (cfg.DUP_W_IMAGE, image_sim)
        applicable_weight = sum(w for w, _ in components.values())
        if applicable_weight <= 0:
            return 0.0
        total = sum(w * sim for w, sim in components.values()) / applicable_weight
        return total * 100.0
