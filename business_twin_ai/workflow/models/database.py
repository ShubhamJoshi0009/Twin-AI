"""SQLAlchemy ORM models for the Status Workflow module.

Two tables power the whole lifecycle feature:

* ``entity_status``      — the *current* state of each entity, with a version
                           counter for optimistic concurrency.
* ``status_transitions`` — an append-only accountability log. Every lifecycle
                           change writes one row here (actor, role, from/to
                           state, action, notes, timestamp) and is never
                           mutated or deleted.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
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


class EntityStatus(Base):
    """Current lifecycle state of one tracked entity (report, rescue, ...)."""

    __tablename__ = "entity_status"
    __table_args__ = (
        # Composite natural key: one row per (entity_type, entity_id).
        UniqueConstraint("entity_type", "entity_id", name="uq_entity_status_type_id"),
        Index("ix_entity_status_type", "entity_type"),
        Index("ix_entity_status_current_state", "current_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    current_state: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic lock
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class StatusTransition(Base):
    """Append-only accountability entry for one lifecycle transition."""

    __tablename__ = "status_transitions"
    __table_args__ = (
        # Timeline / audit queries are always scoped by entity or actor.
        Index("ix_status_transitions_entity", "entity_type", "entity_id", "created_at"),
        Index("ix_status_transitions_actor", "actor_id", "created_at"),
        Index("ix_status_transitions_created_at", "created_at"),
        Index("ix_status_transitions_to_state", "to_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)

    # ── The lifecycle change ───────────────────────────────────────────────
    # from_state is null only for the "register" anchor row (no prior state).
    from_state: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Actor accountability ───────────────────────────────────────────────
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
