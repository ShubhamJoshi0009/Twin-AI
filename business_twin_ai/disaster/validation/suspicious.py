"""Suspicious / fake report detection stage (spec §6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, select

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.models import DisasterReport
from business_twin_ai.disaster.utils.geo import haversine_km, movement_speed_kmh
from business_twin_ai.disaster.utils.text import text_similarity, truncate
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin
from business_twin_ai.disaster.validation.duplicates import _as_utc


@dataclass
class SuspiciousResult:
    """Result of the suspicious-report heuristics."""

    suspicious: bool = False
    reasons: List[str] = field(default_factory=list)


class SuspiciousDetectionStage(TimedStageMixin):
    """Heuristic fraud detection (spec §6).

    Flags are additive: any single heuristic being tripped makes the whole
    report suspicious. All queries are bounded and indexed.
    """

    name = "suspicious"

    async def run(self, context: StageContext) -> SuspiciousResult:
        cfg: ValidationConfig = context.config
        payload = context.payload
        reasons: List[str] = []
        now = datetime.now(timezone.utc)

        # ── Future timestamp ──
        raw_ts = payload.get("timestamp")
        if isinstance(raw_ts, datetime):
            ts = _as_utc(raw_ts)
            if ts > now + timedelta(minutes=cfg.FUTURE_TOLERANCE_MINUTES):
                reasons.append("future timestamp")

        # ── Random coordinates (too few decimal places, e.g. rounded grid) ──
        lat, lon = payload.get("latitude"), payload.get("longitude")
        if lat is not None and lon is not None:
            lat_dec = len(repr(lat).split(".")[1]) if "." in repr(lat) else 0
            lon_dec = len(repr(lon).split(".")[1]) if "." in repr(lon) else 0
            if min(lat_dec, lon_dec) < cfg.SUSPICIOUS_MIN_DECIMALS:
                reasons.append(
                    f"imprecise/rounded coordinates ({lat}, {lon}) look machine-generated"
                )

        # ── GPS far from image GPS ──
        image = context.results.get("image")
        image_gps: Optional[tuple] = None
        if image is not None and image.image_metadata.get("gps"):
            # We do not persist image GPS coordinates in metadata (only a flag);
            # the raw inspection is available through _image_gps when computed.
            image_gps = payload.get("_image_gps")
        if lat is not None and lon is not None and image_gps:
            dist = haversine_km(lat, lon, image_gps[0], image_gps[1])
            if dist > cfg.SUSPICIOUS_IMAGE_GPS_DISTANCE_KM:
                reasons.append(f"reported GPS is {dist:.1f}km from image GPS")

        # ── Very low metadata / image scores ──
        metadata = context.results.get("metadata")
        if metadata is not None and metadata.metadata_score < cfg.LOW_METADATA_SCORE:
            reasons.append(f"very low metadata score ({metadata.metadata_score:.0f})")
        if image is not None and image.present and image.image_score < cfg.LOW_IMAGE_SCORE:
            reasons.append(f"very low image score ({image.image_score:.0f})")

        if context.db is None:
            return SuspiciousResult(suspicious=bool(reasons), reasons=reasons)

        # ── Same reporter sending too many reports (recent window) ──
        reporter_id = payload.get("reporter_id")
        hour_ago = now - timedelta(hours=1)
        if reporter_id:
            count_q = await context.db.execute(
                select(func.count())
                .select_from(DisasterReport)
                .where(
                    DisasterReport.reporter_id == reporter_id,
                    DisasterReport.timestamp >= hour_ago,
                )
            )
            recent_count = count_q.scalar() or 0
            if recent_count >= cfg.SUSPICIOUS_MAX_REPORTS_PER_HOUR:
                reasons.append(
                    f"reporter sent {recent_count} reports in the last hour (flooding)"
                )

        # ── Copied description / reused image / impossible speed ──
        # Compare against the reporter's previous report (for movement speed)
        # and the overall recent pool (for copied text / reused image).
        prev_q = await context.db.execute(
            select(
                DisasterReport.latitude,
                DisasterReport.longitude,
                DisasterReport.timestamp,
                DisasterReport.image_hash,
                DisasterReport.description,
                DisasterReport.title,
            )
            .where(DisasterReport.reporter_id == reporter_id)
            .order_by(DisasterReport.timestamp.desc())
            .limit(1)
        )
        prev = prev_q.mappings().first()

        if prev is not None and lat is not None and lon is not None:
            # ── Impossible movement speed ──
            # Only meaningful over a real time gap; reports seconds apart would
            # otherwise compute absurd speeds from near-zero deltas.
            prev_ts = _as_utc(prev["timestamp"])
            current_ts = ts if isinstance(raw_ts, datetime) else now
            hours = abs(current_ts - prev_ts).total_seconds() / 3600.0
            min_window = cfg.SUSPICIOUS_MIN_SPEED_WINDOW_MINUTES / 60.0
            if hours >= min_window:
                speed = movement_speed_kmh(lat, lon, prev["latitude"], prev["longitude"], hours)
                if speed > cfg.SUSPICIOUS_MAX_SPEED_KMH:
                    reasons.append(f"impossible movement speed ({speed:.0f} km/h)")

        # ── Copied description / reused image against recent pool ──
        pool_q = await context.db.execute(
            select(
                DisasterReport.description,
                DisasterReport.title,
                DisasterReport.image_hash,
            )
            .order_by(DisasterReport.timestamp.desc())
            .limit(20)
        )
        pool = pool_q.mappings().all()

        my_text = truncate(
            f"{payload.get('title', '')} {payload.get('description', '')}",
            cfg.DUP_MAX_TEXT_LENGTH,
        )
        for row in pool:
            row_text = truncate(
                f"{row.get('title', '')} {row.get('description', '')}",
                cfg.DUP_MAX_TEXT_LENGTH,
            )
            if text_similarity(my_text, row_text) >= cfg.SUSPICIOUS_TEXT_SIMILARITY:
                reasons.append("description appears copied from another report")
                break

        payload_hash = payload.get("_image_hash")
        if payload_hash:
            for row in pool:
                if row.get("image_hash") == payload_hash:
                    reasons.append("same image reused across reports")
                    break

        return SuspiciousResult(suspicious=bool(reasons), reasons=reasons)
