"""SQLAlchemy ORM models for the Business Twin AI module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from business_twin_ai.database import Base


class DigitalTwin(Base):
    """Represents an enterprise digital twin – the core entity."""

    __tablename__ = "digital_twins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(128), nullable=False, default="general")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Financial State ──────────────────────────────────
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    expenses: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    cash_flow: Mapped[float] = mapped_column(Float, default=0.0)

    # ── People ───────────────────────────────────────────
    customers: Mapped[int] = mapped_column(Integer, default=0)
    employees: Mapped[int] = mapped_column(Integer, default=0)

    # ── Products & Sales ─────────────────────────────────
    products: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    sales: Mapped[float] = mapped_column(Float, default=0.0)
    marketing_budget: Mapped[float] = mapped_column(Float, default=0.0)
    pricing: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Inventory & Logistics ────────────────────────────
    inventory_summary: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    warehouses: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Market ───────────────────────────────────────────
    competitors: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    market_share: Mapped[float] = mapped_column(Float, default=0.0)

    # ── KPIs ─────────────────────────────────────────────
    kpis: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    business_health_score: Mapped[float] = mapped_column(Float, default=50.0)

    # ── Metadata ─────────────────────────────────────────
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # ── Relationships ────────────────────────────────────
    simulations: Mapped[list["Simulation"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan"
    )
    profile_checklist: Mapped[Optional["ProfileChecklist"]] = relationship(
        back_populates="twin", cascade="all, delete-orphan", uselist=False
    )


class ProfileChecklist(Base):
    """Persisted source-checklist state for a digital twin (saved completions).

    One row per twin. ``sections`` stores the user's completion flags for each
    audited source so the checklist survives across sessions; the coverage
    audit itself is always recomputed on demand.
    """

    __tablename__ = "profile_checklists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("digital_twins.id"),
        nullable=False,
        unique=True,
    )
    # [{source_id: str, completed: bool}, ...]
    sections: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    overall_completion: Mapped[float] = mapped_column(Float, default=0.0)
    completed_count: Mapped[int] = mapped_column(Integer, default=0)
    # Last scheduled audit snapshot — used to detect coverage regressions.
    last_audit_coverage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_audit_verified: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_audited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Cascades with the twin so deleting a profile never orphans its checklist.
    twin: Mapped["DigitalTwin"] = relationship(back_populates="profile_checklist")


class Simulation(Base):
    """A single simulation run against a digital twin."""

    __tablename__ = "simulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("digital_twins.id"), nullable=False
    )
    decision_type: Mapped[str] = mapped_column(String(128), nullable=False)
    decision_params: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Predictions ──────────────────────────────────────
    predicted_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_profit: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_cash_flow: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_customers: Mapped[int] = mapped_column(Integer, default=0)
    predicted_market_share: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_operational_cost: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_roi: Mapped[float] = mapped_column(Float, default=0.0)
    predicted_health_score: Mapped[float] = mapped_column(Float, default=50.0)

    # ── Full prediction payload ──────────────────────────
    predictions: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Scenario Analysis ────────────────────────────────
    scenarios: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Confidence ───────────────────────────────────────
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    confidence_details: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Recommendation ───────────────────────────────────
    recommendation: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Explanation (XAI) ────────────────────────────────
    explanation: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # ── Metadata ─────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # ── Relationships ────────────────────────────────────
    twin: Mapped["DigitalTwin"] = relationship(back_populates="simulations")


class Insight(Base):
    """Auto-generated business insight."""

    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("digital_twins.id"), nullable=False
    )
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False)  # revenue_decline, growth_opportunity, etc.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="info")  # info, warning, critical
    data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Strategy(Base):
    """Generated business strategy."""

    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    twin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("digital_twins.id"), nullable=False
    )
    strategy_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_impact: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
