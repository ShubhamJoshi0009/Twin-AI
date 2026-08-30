"""Status Workflow API routes.

Endpoints (all under ``/api/v1/workflow``):

* ``POST   /{entity_type}/{entity_id}/register``     — start an entity's lifecycle
* ``POST   /{entity_type}/{entity_id}/transitions``  — perform a role-limited transition
* ``GET    /{entity_type}/{entity_id}/status``       — current state + legal next actions
* ``GET    /{entity_type}/{entity_id}/history``      — entity timeline (accountability log)
* ``GET    /definitions``                            — all state machines
* ``GET    /audit``                                  — filtered global audit log
* ``GET    /timeline``                               — dashboard timeline (recent events)

Transition requests carry ``actor_id`` + ``actor_role`` explicitly (no auth
system in this project); the state machine enforces role limits per action.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.database import get_db
from business_twin_ai.workflow.config import (
    TransitionRule,
    WorkflowDefinition,
    all_workflows,
)
from business_twin_ai.workflow.engines.engine import StatusWorkflowEngine, WorkflowError
from business_twin_ai.workflow.models import EntityStatus
from business_twin_ai.workflow.schemas.schemas import (
    AuditLogResponse,
    RegisterEntityRequest,
    StatusOut,
    TimelineEntryOut,
    TransitionOut,
    TransitionRequest,
    TransitionResponse,
    WorkflowDefinitionOut,
    WorkflowDefinitionsResponse,
)

router = APIRouter()


def _raise(exc: WorkflowError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.message)


# ── Lifecycle actions ─────────────────────────────────────────────────────────

@router.post(
    "/{entity_type}/{entity_id}/register",
    response_model=StatusOut,
    status_code=201,
)
async def register_entity(
    entity_type: str,
    entity_id: str,
    payload: RegisterEntityRequest,
    db: AsyncSession = Depends(get_db),
) -> StatusOut:
    """Register an entity at its lifecycle's initial state (idempotent)."""
    engine = StatusWorkflowEngine(db)
    try:
        status = await engine.register_entity(
            entity_type,
            entity_id,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            notes=payload.notes,
        )
    except WorkflowError as exc:
        _raise(exc)
    await db.commit()
    # created_at / updated_at are server-side defaults — load them so
    # response shaping does not trigger a lazy load outside the greenlet.
    await db.refresh(status)
    return _status_out(status, engine)


@router.post(
    "/{entity_type}/{entity_id}/transitions",
    response_model=TransitionResponse,
    status_code=200,
)
async def create_transition(
    entity_type: str,
    entity_id: str,
    payload: TransitionRequest,
    db: AsyncSession = Depends(get_db),
) -> TransitionResponse:
    """Perform a role-limited lifecycle transition with accountability log."""
    engine = StatusWorkflowEngine(db)
    try:
        transition, status = await engine.transit(
            entity_type,
            entity_id,
            action=payload.action,
            actor_id=payload.actor_id,
            actor_role=payload.actor_role,
            notes=payload.notes,
        )
    except WorkflowError as exc:
        _raise(exc)
    await db.commit()
    # Load server-side defaults (created_at) before shaping the response.
    await db.refresh(transition)
    await db.refresh(status)
    return TransitionResponse(
        transition=TransitionOut.model_validate(transition),
        status=_status_out(status, engine),
    )


# ── Reads ─────────────────────────────────────────────────────────────────────

@router.get("/{entity_type}/{entity_id}/status", response_model=StatusOut)
async def get_entity_status(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> StatusOut:
    """Current lifecycle state and legal next actions for one entity."""
    engine = StatusWorkflowEngine(db)
    try:
        status = await engine.get_status(entity_type, entity_id)
        if status is None:
            raise WorkflowError(
                404,
                f"Entity {entity_type} '{entity_id}' is not registered. "
                "POST it to /workflow/{type}/{id}/register first.",
            )
    except WorkflowError as exc:
        _raise(exc)
    return _status_out(status, engine)


@router.get(
    "/{entity_type}/{entity_id}/history",
    response_model=list[TimelineEntryOut],
)
async def get_entity_history(
    entity_type: str,
    entity_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEntryOut]:
    """Full accountability timeline for one entity (oldest first)."""
    engine = StatusWorkflowEngine(db)
    # Align with GET /status: an unregistered entity is a 404, not an
    # empty list (so callers can distinguish "no events" from "no entity").
    try:
        status = await engine.get_status(entity_type, entity_id)
        if status is None:
            raise WorkflowError(
                404,
                f"Entity {entity_type} '{entity_id}' is not registered. "
                "POST it to /workflow/{type}/{id}/register first.",
            )
        history = await engine.history(entity_type, entity_id)
    except WorkflowError as exc:
        _raise(exc)
    return [TimelineEntryOut.model_validate(t) for t in history]


# ── Global views ──────────────────────────────────────────────────────────────

@router.get("/definitions", response_model=WorkflowDefinitionsResponse)
async def get_definitions() -> WorkflowDefinitionsResponse:
    """All registered state machines (roles, transitions, initial states)."""
    return WorkflowDefinitionsResponse(
        workflows=[_definition_out(wf) for wf in all_workflows()]
    )


@router.get("/audit", response_model=AuditLogResponse)
async def get_audit_log(
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    to_state: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Filtered, newest-first view of the global accountability log."""
    engine = StatusWorkflowEngine(db)
    total, entries = await engine.audit(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        to_state=to_state,
        limit=limit,
    )
    return AuditLogResponse(
        total=total,
        limit=limit,
        entries=[TimelineEntryOut.model_validate(t) for t in entries],
    )


@router.get("/timeline", response_model=list[TimelineEntryOut])
async def get_dashboard_timeline(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[TimelineEntryOut]:
    """Most recent lifecycle events across all entities (dashboard feed)."""
    engine = StatusWorkflowEngine(db)
    entries = await engine.timeline(limit=limit)
    return [TimelineEntryOut.model_validate(t) for t in entries]


# ── Shapers ───────────────────────────────────────────────────────────────────

def _status_out(status: EntityStatus, engine: StatusWorkflowEngine) -> StatusOut:
    actions = engine.workflow(status.entity_type).transitions_from(
        status.current_state
    )
    return StatusOut(
        entity_type=status.entity_type,
        entity_id=status.entity_id,
        current_state=status.current_state,
        version=status.version,
        updated_at=status.updated_at,
        available_actions=[_action_out(rule) for rule in actions],
    )


def _action_out(rule: TransitionRule) -> dict:
    return {
        "action": rule.action,
        "to_state": rule.to_state,
        "requires_notes": rule.requires_notes,
        "description": rule.description,
    }


def _definition_out(wf: WorkflowDefinition) -> WorkflowDefinitionOut:
    return WorkflowDefinitionOut(
        entity_type=wf.entity_type,
        label=wf.label,
        initial_state=wf.initial_state,
        states=list(wf.states),
        description=wf.description,
        transitions=[
            {
                "from_state": t.from_state,
                "to_state": t.to_state,
                "action": t.action,
                "allowed_roles": list(t.allowed_roles),
                "requires_notes": t.requires_notes,
                "description": t.description,
            }
            for t in wf.transitions
        ],
    )
