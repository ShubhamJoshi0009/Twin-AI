"""Location validation stage (spec §1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.utils.geo import is_origin, is_valid_gps, precision_score
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin


@dataclass
class LocationResult:
    """Result of location validation."""

    valid_location: bool
    precision_score: float = 0.0
    location_verified: bool = False
    location_score: float = 0.0
    reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class LocationValidationStage(TimedStageMixin):
    """Validates latitude/longitude range, (0,0) origin, names and precision."""

    name = "location"

    async def run(self, context: StageContext) -> LocationResult:
        cfg: ValidationConfig = context.config
        payload = context.payload

        lat = payload.get("latitude")
        lon = payload.get("longitude")

        # 1) Coordinates exist?
        if lat is None or lon is None:
            return LocationResult(
                valid_location=False,
                reason="missing latitude/longitude",
                warnings=["latitude or longitude is missing"],
            )

        # 2) Valid GPS range?
        if not is_valid_gps(lat, lon, cfg):
            return LocationResult(
                valid_location=False,
                reason="Coordinates outside allowed range",
                warnings=[f"lat={lat} lon={lon} out of GPS range"],
            )

        # 3) Not (0,0)?
        if is_origin(lat, lon, cfg):
            return LocationResult(
                valid_location=False,
                reason="Coordinates are (0,0) — missing location",
                warnings=["coordinates are (0,0)"],
            )

        # 4) Location name / district / state presence.
        location_name = (payload.get("location_name") or "").strip()
        district = (payload.get("district") or "").strip()
        state = (payload.get("state") or "").strip()

        warnings: List[str] = []
        if not location_name:
            warnings.append("location_name missing")
        if not district:
            warnings.append("district missing")
        if not state:
            warnings.append("state missing")

        # 5) GPS precision score (decimal places of both coords).
        precision = precision_score(lat, lon, cfg)

        # 6) Reverse geocode (optional extension point — off by default).
        location_verified = bool(location_name)
        reason: Optional[str] = None
        if cfg.REVERSE_GEOCODE_ENABLED:
            # Extension point: call a geocoding adapter here. When disabled we
            # treat the supplied names as self-verified if location_name exists.
            pass

        # Composite location score (0-100): precision is the backbone, name
        # presence and admin details add confidence.
        score = precision
        if location_name:
            score += cfg.BONUS_LOCATION_NAME
        if district and state:
            score += cfg.BONUS_DISTRICT_STATE
        score = min(100.0, round(score, 2))

        return LocationResult(
            valid_location=True,
            precision_score=round(precision, 2),
            location_verified=location_verified,
            location_score=score,
            reason=reason,
            warnings=warnings,
        )
