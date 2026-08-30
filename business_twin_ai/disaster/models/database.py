"""SQLAlchemy ORM models for the Disaster Report Validation module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from business_twin_ai.database import Base


class DisasterReport(Base):
    """A single validated disaster/emergency report."""

    __tablename__ = "disaster_reports"
    __table_args__ = (
        # Spatial + temporal + reporter indexes (spec: cluster_id, location,
        # timestamp, reporter_id, duplicate).
        Index("ix_disaster_reports_cluster_id", "cluster_id"),
        Index("ix_disaster_reports_location", "latitude", "longitude"),
        Index("ix_disaster_reports_timestamp", "timestamp"),
        Index("ix_disaster_reports_reporter_id", "reporter_id"),
        Index("ix_disaster_reports_duplicate", "duplicate"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Report metadata ────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reporter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    disaster_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[float] = mapped_column(Float, nullable=False)  # 0-10

    # ── Location ───────────────────────────────────────────────────────────
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # ── Image ──────────────────────────────────────────────────────────────
    image_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    image_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ── Validation scores & flags (spec §13) ───────────────────────────────
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_score: Mapped[float] = mapped_column(Float, default=0.0)
    image_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate_score: Mapped[float] = mapped_column(Float, default=0.0)
    duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    cluster_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    warning_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(16), default="valid")
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_notes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    reporter_trust_score: Mapped[float] = mapped_column(Float, default=50.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IncidentCluster(Base):
    """An incident cluster grouping nearby, temporally-close reports."""

    __tablename__ = "incident_clusters"
    __table_args__ = (
        Index("ix_incident_clusters_center", "center_latitude", "center_longitude"),
        Index("ix_incident_clusters_type", "disaster_type"),
        UniqueConstraint("cluster_id", name="uq_incident_clusters_cluster_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cluster_id: Mapped[str] = mapped_column(String(36), nullable=False)
    disaster_type: Mapped[str] = mapped_column(String(64), nullable=False)
    center_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    center_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=1)
    average_severity: Mapped[float] = mapped_column(Float, default=0.0)
    last_update: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    warning_level: Mapped[str] = mapped_column(String(16), default="GREEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ReporterProfile(Base):
    """Trust + verification history for a reporter."""

    __tablename__ = "reporter_profiles"

    reporter_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    reporter_trust_score: Mapped[float] = mapped_column(Float, default=50.0)
    total_reports: Mapped[int] = mapped_column(Integer, default=0)
    accepted_reports: Mapped[int] = mapped_column(Integer, default=0)
    rejected_reports: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_reports: Mapped[int] = mapped_column(Integer, default=0)
    false_reports: Mapped[int] = mapped_column(Integer, default=0)
    verification_history: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_report_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
