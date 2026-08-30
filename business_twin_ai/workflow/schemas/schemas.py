"""Pydantic schemas for the Status Workflow module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from business_twin_ai.workflow.config import ALL_ROLES


def validate_role(value: str) -> str:
    """Shared role check used by every actor-carrying schema."""
    if value not in ALL_ROLES:
        raise ValueError(
            f"Unknown role '{value}'. Allowed roles: {', '.join(ALL_ROLES)}"
        )
    return value


# ═══════════════════════════════════════════════════════════════════════════════
# Incoming transition request
# ═══════════════════════════════════════════════════════════════════════════════

class TransitionRequest(BaseModel):
    """Body for ``POST /workflow/{entity_type}/{entity_id}/transitions``.

    ``actor_role`` limits which roles may perform the action (the state
    machine in config.py declares the allowed roles per transition). In
    production this would come from an authenticated session / JWT; here it
    is explicit so the workflow layer stays pluggable.
    """

    action: str = Field(..., min_length=1, max_length=64)
    actor_id: str = Field(..., min_length=1, max_length=128)
    actor_role: str = Field(..., min_length=1, max_length=32)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("actor_role")
    @classmethod
    def _role_must_exist(cls, value: str) -> str:
        return validate_role(value)


class RegisterEntityRequest(BaseModel):
    """Body for ``POST /workflow/{entity_type}/{entity_id}/register``."""

    actor_id: str = Field(..., min_length=1, max_length=128)
    actor_role: str = Field(..., min_length=1, max_length=32)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("actor_role")
    @classmethod
    def _role_must_exist(cls, value: str) -> str:
        return validate_role(value)


# ═══════════════════════════════════════════════════════════════════════════════
# Read models
# ═══════════════════════════════════════════════════════════════════════════════

class TransitionOut(BaseModel):
    """One audit-log row describing a lifecycle change."""

    id: uuid.UUID
    entity_type: str
    entity_id: str
    from_state: Optional[str] = None  # null only for the "register" anchor
    to_state: str
    action: str
    actor_id: str
    actor_role: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AvailableActionOut(BaseModel):
    """A legal next action from the current state, for driving dashboards."""

    action: str
    to_state: str
    requires_notes: bool
    description: str = ""


class StatusOut(BaseModel):
    """Current lifecycle state of one entity plus its legal next actions."""

    entity_type: str
    entity_id: str
    current_state: str
    version: int
    updated_at: datetime
    available_actions: List[AvailableActionOut] = Field(default_factory=list)


class TransitionResponse(BaseModel):
    """Envelope returned by a successful transition."""

    transition: TransitionOut
    status: StatusOut


class TimelineEntryOut(BaseModel):
    """One event on the dashboard timeline (any entity)."""

    id: uuid.UUID
    entity_type: str
    entity_id: str
    action: str
    from_state: Optional[str] = None  # null only for the "register" anchor
    to_state: str
    actor_id: str
    actor_role: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Definitions (state machines) — read-only
# ═══════════════════════════════════════════════════════════════════════════════

class TransitionRuleOut(BaseModel):
    """One allowed edge in a workflow definition."""

    from_state: str
    to_state: str
    action: str
    allowed_roles: List[str]
    requires_notes: bool
    description: str = ""


class WorkflowDefinitionOut(BaseModel):
    """A complete state machine for one entity type."""

    entity_type: str
    label: str
    initial_state: str
    states: List[str]
    description: str = ""
    transitions: List[TransitionRuleOut] = Field(default_factory=list)


class WorkflowDefinitionsResponse(BaseModel):
    """All registered state machines."""

    workflows: List[WorkflowDefinitionOut] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Audit log
# ═══════════════════════════════════════════════════════════════════════════════

class AuditLogResponse(BaseModel):
    """Paged audit-log query result."""

    total: int
    limit: int
    entries: List[TimelineEntryOut] = Field(default_factory=list)
