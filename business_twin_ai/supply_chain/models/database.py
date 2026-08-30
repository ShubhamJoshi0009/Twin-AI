"""SQLAlchemy ORM models for the Supply Chain AI module."""

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


class Supplier(Base):
    """Supplier information and performance tracking."""

    __tablename__ = "sc_suppliers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    product_categories: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)
    cost_per_unit: Mapped[float] = mapped_column(Float, default=0.0)
    capacity: Mapped[int] = mapped_column(Integer, default=1000)
    quality_rating: Mapped[float] = mapped_column(Float, default=5.0)
    reliability_score: Mapped[float] = mapped_column(Float, default=80.0)
    contract_expiry: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivery_history: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    performance_history: Mapped[Optional[dict]] = mapped_column(JSON, default=list)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="supplier")


class Warehouse(Base):
    """Warehouse information and utilization tracking."""

    __tablename__ = "sc_warehouses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=10000)
    utilization: Mapped[float] = mapped_column(Float, default=0.0)
    storage_cost_per_unit: Mapped[float] = mapped_column(Float, default=1.0)
    efficiency_score: Mapped[float] = mapped_column(Float, default=80.0)
    incoming_shipments: Mapped[int] = mapped_column(Integer, default=0)
    outgoing_shipments: Mapped[int] = mapped_column(Integer, default=0)
    manager: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="warehouse")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="warehouse")


class InventoryItem(Base):
    """Inventory tracking across warehouses."""

    __tablename__ = "sc_inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_warehouses.id"), nullable=False
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="general")
    current_stock: Mapped[int] = mapped_column(Integer, default=0)
    reorder_level: Mapped[int] = mapped_column(Integer, default=100)
    safety_stock: Mapped[int] = mapped_column(Integer, default=50)
    max_stock: Mapped[int] = mapped_column(Integer, default=5000)
    incoming_stock: Mapped[int] = mapped_column(Integer, default=0)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost: Mapped[float] = mapped_column(Float, default=0.0)
    turnover_rate: Mapped[float] = mapped_column(Float, default=0.0)
    expiry_date: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_restocked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventory_items")


class Shipment(Base):
    """Shipment and logistics tracking."""

    __tablename__ = "sc_shipments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_suppliers.id"), nullable=False
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sc_warehouses.id"), nullable=False
    )
    shipment_number: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, in_transit, delivered, delayed
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    vehicle_info: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    route: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    origin: Mapped[str] = mapped_column(String(255), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fuel_cost: Mapped[float] = mapped_column(Float, default=0.0)
    transport_cost: Mapped[float] = mapped_column(Float, default=0.0)
    route_efficiency: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    supplier: Mapped["Supplier"] = relationship(back_populates="shipments")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="shipments")


class SupplyChainRisk(Base):
    """Detected supply chain risks."""

    __tablename__ = "sc_risks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    risk_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="medium")  # low, medium, high, critical
    probability: Mapped[float] = mapped_column(Float, default=50.0)
    risk_score: Mapped[float] = mapped_column(Float, default=50.0)
    business_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(32), default="medium")
    affected_entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    affected_entity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, mitigated, resolved
    mitigation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplyChainAlert(Base):
    """Real-time supply chain alerts."""

    __tablename__ = "sc_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="info")  # info, warning, critical
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, acknowledged, resolved
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplyChainScenario(Base):
    """Supply chain scenario simulations."""

    __tablename__ = "sc_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_type: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    impact: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    recommendations: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
