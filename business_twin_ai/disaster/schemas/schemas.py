"""Pydantic schemas for the Disaster Report Validation module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════════
# Incoming report
# ═══════════════════════════════════════════════════════════════════════════════

class DisasterReportCreate(BaseModel):
    """Payload accepted by every report-creation API."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1, max_length=5000)
    timestamp: Optional[datetime] = None  # defaults to now when omitted
    reporter_id: str = Field(..., min_length=1, max_length=128)
    disaster_type: str = Field(..., min_length=1, max_length=64)
    severity: float = Field(..., ge=0, le=10)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = Field(None, max_length=255)
    district: Optional[str] = Field(None, max_length=128)
    state: Optional[str] = Field(None, max_length=128)
    # Optional raw image bytes (base64) — missing images reduce confidence
    # but never reject the report.
    image_base64: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Validation outputs
# ═══════════════════════════════════════════════════════════════════════════════

class LocationValidationResult(BaseModel):
    """Output of the location stage (spec §1)."""

    valid_location: bool
    precision_score: float
    location_verified: bool
    reason: Optional[str] = None


class MetadataValidationResult(BaseModel):
    """Output of the metadata stage (spec §2)."""

    metadata_score: float
    valid: bool
    warnings: List[str] = Field(default_factory=list)


class ImageValidationResult(BaseModel):
    """Output of the image stage (spec §3)."""

    image_valid: bool
    image_score: float
    image_metadata: Dict[str, Any] = Field(default_factory=dict)


class DuplicateValidationResult(BaseModel):
    """Output of the duplicate stage (spec §4)."""

    duplicate: bool
    duplicate_score: float
    duplicate_of: Optional[str] = None
    candidates_checked: int = 0


class SuspiciousValidationResult(BaseModel):
    """Output of the suspicious stage (spec §6)."""

    suspicious: bool
    reasons: List[str] = Field(default_factory=list)


class ConfidenceValidationResult(BaseModel):
    """Output of the confidence stage (spec §7)."""

    confidence_score: float
    components: Dict[str, float] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    """Full per-report validation summary (spec §9)."""

    valid: bool
    confidence_score: float
    location_score: float
    metadata_score: float
    image_score: float
    duplicate: bool
    duplicate_score: float
    suspicious: bool
    suspicious_reasons: List[str] = Field(default_factory=list)
    cluster_id: Optional[str] = None
    warning_level: Optional[str] = None
    validation_status: str = "valid"
    reporter_trust_score: float = 50.0
    execution_time_ms: float = 0.0
    location: LocationValidationResult
    metadata: MetadataValidationResult
    image: ImageValidationResult
    duplicate_details: DuplicateValidationResult
    suspicious_details: SuspiciousValidationResult
    confidence: ConfidenceValidationResult
    validation_notes: List[str] = Field(default_factory=list)


class ReportValidationResponse(BaseModel):
    """Response envelope for report creation/validation (spec §9)."""

    report_id: str
    validation: ValidationResult


# ═══════════════════════════════════════════════════════════════════════════════
# Stored report / cluster / map read models
# ═══════════════════════════════════════════════════════════════════════════════

class DisasterReportOut(BaseModel):
    """A stored, validated report."""

    id: uuid.UUID
    title: str
    description: str
    timestamp: datetime
    reporter_id: str
    disaster_type: str
    severity: float
    latitude: float
    longitude: float
    location_name: Optional[str]
    district: Optional[str]
    state: Optional[str]
    location_score: float
    metadata_score: float
    image_score: float
    confidence_score: float
    duplicate_score: float
    duplicate: bool
    duplicate_of: Optional[str]
    cluster_id: Optional[str]
    warning_level: Optional[str]
    validation_status: str
    suspicious: bool
    validation_notes: Optional[list]
    reporter_trust_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentClusterOut(BaseModel):
    """An incident cluster with its warning state."""

    id: uuid.UUID
    cluster_id: str
    disaster_type: str
    center_latitude: float
    center_longitude: float
    report_count: int
    average_severity: float
    last_update: datetime
    warning_level: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MapWarningOut(BaseModel):
    """Per-cluster warning entry for the disaster map (spec §10)."""

    cluster_id: str
    disaster_type: str
    warning_level: str
    active_reports: int
    cluster_size: int  # aliased to report_count for readability
    average_severity: float
    center_latitude: float
    center_longitude: float
    last_update: datetime


class MapWarningResponse(BaseModel):
    """Aggregate map warning state (spec §10)."""

    generated_at: datetime
    warnings: List[MapWarningOut] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)  # level -> count
