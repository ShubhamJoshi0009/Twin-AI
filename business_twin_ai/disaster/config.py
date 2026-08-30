"""Tunable thresholds and weights for the disaster report validation layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

# ruff: noqa: UP006, UP035 — keep `typing.List` for clarity in public config.


@dataclass(frozen=True)
class ValidationConfig:
    """Central configuration for every validation stage.

    All thresholds live here so the pipeline can be tuned without touching
    stage logic. Frozen on purpose — treat it as a read-only settings object.
    """

    # ── Location validation ────────────────────────────────────────────────
    GPS_LAT_MIN: float = -90.0
    GPS_LAT_MAX: float = 90.0
    GPS_LON_MIN: float = -180.0
    GPS_LON_MAX: float = 180.0
    ORIGIN_TOLERANCE: float = 1e-6  # |lat|,|lon| below this is treated as (0, 0)

    # Precision scoring by decimal places (scale 0-100).
    PRECISION_SCORE_BY_DECIMALS: Tuple[int, ...] = (10, 30, 50, 65, 80, 90, 100)

    # ── Metadata validation ────────────────────────────────────────────────
    REQUIRED_FIELDS: Tuple[str, ...] = (
        "title",
        "description",
        "timestamp",
        "reporter_id",
        "disaster_type",
        "severity",
    )
    MIN_TITLE_LENGTH: int = 5
    MIN_DESCRIPTION_LENGTH: int = 20
    MAX_DESCRIPTION_LENGTH: int = 5000
    FUTURE_TOLERANCE_MINUTES: int = 10  # allow small clock skew
    SPAM_WORDS: Tuple[str, ...] = (
        "urgent!!",
        "claim your",
        "act now",
        "limited time",
        "free prize",
        "winner",
        "congratulations",
        "click here",
        "100% guaranteed",
        "cash reward",
        "exclusive offer",
    )
    REPEATED_CHAR_RUN: int = 5  # e.g. "aaaaa" counts as repeated characters
    LOW_METADATA_SCORE: float = 30.0

    # ── Image validation (pure-Python inspector, no external deps) ─────────
    ALLOWED_IMAGE_FORMATS: Tuple[str, ...] = ("jpeg", "png", "gif", "webp", "bmp")
    MAX_IMAGE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MIN_IMAGE_BYTES: int = 100
    MAX_IMAGE_DIMENSION: int = 20000
    MIN_IMAGE_DIMENSION: int = 8
    IMAGE_NO_IMAGE_SCORE: float = 50.0  # missing image halves the image component
    LOW_IMAGE_SCORE: float = 30.0

    # ── Duplicate detection ────────────────────────────────────────────────
    DUPLICATE_THRESHOLD: float = 85.0
    DUP_NEARBY_RADIUS_KM: float = 5.0
    DUP_TIME_WINDOW_HOURS: float = 24.0
    DUP_QUERY_LIMIT: int = 50
    DUP_MAX_TEXT_LENGTH: int = 500

    # Weights for duplicate similarity components (must sum to 1.0).
    DUP_W_LOCATION: float = 0.30
    DUP_W_TIME: float = 0.20
    DUP_W_IMAGE: float = 0.20
    DUP_W_TEXT: float = 0.15
    DUP_W_TYPE: float = 0.10
    DUP_W_SEVERITY: float = 0.05

    # ── Clustering ─────────────────────────────────────────────────────────
    CLUSTER_RADIUS_KM: float = 10.0
    CLUSTER_TIME_WINDOW_HOURS: float = 48.0
    CLUSTER_MAX_QUERY: int = 200
    CLUSTER_ID_PREFIX: str = "cluster_"

    # ── Suspicious heuristics ──────────────────────────────────────────────
    SUSPICIOUS_IMAGE_GPS_DISTANCE_KM: float = 10.0
    SUSPICIOUS_MAX_REPORTS_PER_HOUR: int = 10
    SUSPICIOUS_TEXT_SIMILARITY: float = 0.90
    SUSPICIOUS_MAX_SPEED_KMH: float = 900.0  # no civilian transport is faster
    # Only judge movement speed when the time gap is meaningful — reports
    # seconds apart would otherwise compute absurd speeds from tiny deltas.
    SUSPICIOUS_MIN_SPEED_WINDOW_MINUTES: float = 6.0
    SUSPICIOUS_MIN_DECIMALS: int = 2  # fewer decimals → "random" coordinates

    # ── Confidence score weights (spec: 30/20/20/15/15) ────────────────────
    CONF_W_LOCATION: float = 0.30
    CONF_W_METADATA: float = 0.20
    CONF_W_IMAGE: float = 0.20
    CONF_W_DUPLICATE: float = 0.15
    CONF_W_TRUST: float = 0.15

    # ── Reporter trust ─────────────────────────────────────────────────────
    TRUST_START: float = 50.0
    TRUST_ACCEPTED_DELTA: float = 2.0
    TRUST_REJECTED_DELTA: float = -10.0
    TRUST_DUPLICATE_DELTA: float = -3.0
    TRUST_SUSPICIOUS_DELTA: float = -5.0
    TRUST_FALSE_REPORT_DELTA: float = -15.0
    TRUST_MIN: float = 0.0
    TRUST_MAX: float = 100.0

    # ── Map warning state ──────────────────────────────────────────────────
    WARN_RED_SEVERITY: float = 8.0
    WARN_RED_REPORTS: int = 20
    WARN_ORANGE_SEVERITY: float = 7.0
    WARN_ORANGE_REPORTS: int = 10
    WARN_YELLOW_SEVERITY: float = 4.0
    WARN_YELLOW_REPORTS: int = 3
    WARN_GREEN_SEVERITY: float = 3.0
    WARN_GREEN_REPORTS: int = 3
    WARNING_LEVELS: Tuple[str, ...] = ("GREEN", "YELLOW", "ORANGE", "RED")
    # Cache cluster/warning lookups for this many seconds.
    WARNING_CACHE_TTL_SECONDS: int = 30

    # ── Validation status values ───────────────────────────────────────────
    STATUS_VALID: str = "valid"
    STATUS_FLAGGED: str = "flagged"
    STATUS_DUPLICATE: str = "duplicate"
    STATUS_REJECTED: str = "rejected"

    # Extension points: reverse-geocoding and image analysis adapters.
    REVERSE_GEOCODE_ENABLED: bool = False
    IMAGE_ANALYSIS_ASYNC: bool = False

    # Extra penalties / bonuses (0-100 scale adjustments).
    PENALTY_MISSING_FIELD: float = 15.0
    PENALTY_SHORT_TEXT: float = 10.0
    PENALTY_SPAM: float = 10.0
    PENALTY_REPEATED_CHARS: float = 10.0
    PENALTY_INVALID_TIMESTAMP: float = 20.0
    PENALTY_FUTURE_TIMESTAMP: float = 10.0
    BONUS_LOCATION_NAME: float = 5.0
    BONUS_DISTRICT_STATE: float = 5.0

    duplicate_candidate_columns: Tuple[str, ...] = field(
        default=(
            "id", "title", "description", "timestamp", "reporter_id",
            "disaster_type", "severity", "latitude", "longitude",
            "image_hash", "cluster_id",
        )
    )
    """Columns selected when scanning for duplicate candidates (perf hint)."""


config = ValidationConfig()
