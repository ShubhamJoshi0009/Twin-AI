"""Status Workflow Engine — lifecycle transitions with an accountability log.

The engine is intentionally free of any HTTP concerns. It validates a
requested transition against the state machine declared in
``workflow.config``, enforces role limits, writes the append-only
``StatusTransition`` audit row, and advances the entity's current state.

Design notes
------------
* Entities are registered lazily: ``transit`` on an unknown entity raises
  404; callers register entities first (via ``register_entity``) so there is
  always a timestamped, actor-attributed "created" audit trail.
* Every transition is a single transaction (audit row + status update), so
  the accountability log can never disagree with the current state.
* The ``version`` counter on ``EntityStatus`` provides optimistic
  concurrency control: transitions apply via a conditional ``UPDATE ...
  WHERE version = :expected``, so a concurrent edit surfaces as a 409
  instead of silently double-applying an action.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.workflow.config import (
    TransitionRule,
    WorkflowDefinition,
    get_workflow,
)
from business_twin_ai.workflow.models import EntityStatus, StatusTransition

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Domain error with an HTTP-friendly status code and message."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class StatusWorkflowEngine:
    """Per-session workflow engine: one instance per request/session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Definitions ─────────────────────────────────────────────────────────

    @staticmethod
    def workflow(entity_type: str) -> WorkflowDefinition:
        wf = get_workflow(entity_type)
        if wf is None:
            known = sorted(_known_types())
            raise WorkflowError(
                404,
                f"Unknown entity type '{entity_type}'. "
                f"Known types: {', '.join(known)}",
            )
        return wf

    # ── Registration ────────────────────────────────────────────────────────

    async def register_entity(
        self,
        entity_type: str,
        entity_id: str,
        actor_id: str = "system",
        actor_role: str = "admin",
        notes: Optional[str] = None,
    ) -> EntityStatus:
        """Create an entity at its lifecycle's initial state (idempotent).

        Returns the existing status when the entity is already registered;
        the first registration also writes the audit entry that anchors the
        entity's timeline.
        """
        wf = self.workflow(entity_type)
        existing = await self._load_status(entity_type, entity_id)
        if existing is not None:
            return existing

        status = EntityStatus(
            entity_type=entity_type,
            entity_id=entity_id,
            current_state=wf.initial_state,
            version=1,
        )
        self.db.add(status)
        self.db.add(
            StatusTransition(
                entity_type=entity_type,
                entity_id=entity_id,
                from_state=None,
                to_state=wf.initial_state,
                action="register",
                actor_id=actor_id,
                actor_role=actor_role,
                notes=notes or f"{wf.label} registered",
            )
        )
        # Two concurrent registrations for the same entity must not create
        # duplicate rows — flush so the unique constraint fires here rather
        # than on the route's commit.
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            existing = await self._load_status(entity_type, entity_id)
            if existing is None:
                raise WorkflowError(500, "Registration failed; please retry") from exc
            return existing
        logger.info(
            "workflow.register entity_type=%s entity_id=%s state=%s actor=%s",
            entity_type,
            entity_id,
            wf.initial_state,
            actor_id,
        )
        return status

    # ── Reads ───────────────────────────────────────────────────────────────

    async def get_status(
        self, entity_type: str, entity_id: str
    ) -> Optional[EntityStatus]:
        return await self._load_status(entity_type, entity_id)

    async def available_actions(
        self, entity_type: str, entity_id: str
    ) -> List[TransitionRule]:
        """Legal next actions for an entity's current state (any role)."""
        wf = self.workflow(entity_type)
        status = await self._require_status(entity_type, entity_id)
        return wf.transitions_from(status.current_state)

    async def history(
        self, entity_type: str, entity_id: str
    ) -> List[StatusTransition]:
        """Full audit trail for one entity, oldest first."""
        result = await self.db.execute(
            select(StatusTransition)
            .where(
                StatusTransition.entity_type == entity_type,
                StatusTransition.entity_id == entity_id,
            )
            .order_by(StatusTransition.created_at.asc())
        )
        return list(result.scalars().all())

    async def audit(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        to_state: Optional[str] = None,
        limit: int = 100,
    ) -> tuple[int, List[StatusTransition]]:
        """Filtered view of the global accountability log.

        Returns ``(total_matching, newest_first_entries)`` where the total is
        the true count *before* ``limit`` is applied.
        """
        conditions = []
        if entity_type:
            conditions.append(StatusTransition.entity_type == entity_type)
        if entity_id:
            conditions.append(StatusTransition.entity_id == entity_id)
        if actor_id:
            conditions.append(StatusTransition.actor_id == actor_id)
        if to_state:
            conditions.append(StatusTransition.to_state == to_state)

        count_stmt = select(func.count()).select_from(StatusTransition)
        for cond in conditions:
            count_stmt = count_stmt.where(cond)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = select(StatusTransition)
        for cond in conditions:
            stmt = stmt.where(cond)
        stmt = stmt.order_by(StatusTransition.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return int(total), list(result.scalars().all())

    async def timeline(self, limit: int = 50) -> List[StatusTransition]:
        """Most recent events across all entities (dashboard timeline)."""
        result = await self.db.execute(
            select(StatusTransition)
            .order_by(StatusTransition.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Transitions ─────────────────────────────────────────────────────────

    async def transit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str,
        actor_role: str,
        notes: Optional[str] = None,
        metadata_: Optional[Dict[str, Any]] = None,
    ) -> tuple[StatusTransition, EntityStatus]:
        """Validate and apply one lifecycle transition.

        Raises :class:`WorkflowError` for unknown workflows/entities (404),
        illegal transitions (422), missing required notes (422) or
        unauthorized roles (403). Nothing is written on failure.
        """
        wf = self.workflow(entity_type)
        status = await self._require_status(entity_type, entity_id)

        # Resolve the edge by (from_state, action) — the same action can lead
        # to different states from different source states (e.g. "cancel").
        rule = _find_rule_by_action(wf, status.current_state, action)
        if rule is None:
            raise WorkflowError(
                422,
                f"Transition '{action}' is not allowed from state "
                f"'{status.current_state}' for {entity_type} {entity_id}",
            )
        if actor_role not in rule.allowed_roles:
            raise WorkflowError(
                403,
                f"Role '{actor_role}' is not allowed to perform "
                f"'{action}' ({rule.from_state} → {rule.to_state}). "
                f"Allowed: {', '.join(rule.allowed_roles)}",
            )
        if rule.requires_notes and not (notes and notes.strip()):
            raise WorkflowError(
                422,
                f"Transition '{action}' requires notes explaining the change",
            )

        transition = StatusTransition(
            entity_type=entity_type,
            entity_id=entity_id,
            from_state=status.current_state,
            to_state=rule.to_state,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            notes=notes,
            metadata_=metadata_,
        )

        # Optimistic concurrency: only apply if the version is unchanged since
        # we read it. A concurrent edit surfaces as 409 and nothing is written.
        expected_version = status.version
        result = await self.db.execute(
            update(EntityStatus)
            .where(
                EntityStatus.entity_type == entity_type,
                EntityStatus.entity_id == entity_id,
                EntityStatus.version == expected_version,
            )
            .values(
                current_state=rule.to_state,
                version=expected_version + 1,
                updated_at=func.now(),
            )
        )
        if result.rowcount == 0:
            raise WorkflowError(
                409,
                f"{entity_type} {entity_id} was modified concurrently; refresh and retry",
            )
        status.current_state = rule.to_state
        status.version = expected_version + 1
        self.db.add(transition)
        # updated_at handled by the onupdate server hook on commit.

        logger.info(
            "workflow.transit entity_type=%s entity_id=%s %s→%s action=%s actor=%s(%s)",
            entity_type,
            entity_id,
            transition.from_state,
            transition.to_state,
            action,
            actor_id,
            actor_role,
        )
        return transition, status

    # ── Internals ───────────────────────────────────────────────────────────

    async def _load_status(
        self, entity_type: str, entity_id: str
    ) -> Optional[EntityStatus]:
        result = await self.db.execute(
            select(EntityStatus).where(
                EntityStatus.entity_type == entity_type,
                EntityStatus.entity_id == entity_id,
            )
        )
        return result.scalar_one_or_none()

    async def _require_status(
        self, entity_type: str, entity_id: str
    ) -> EntityStatus:
        status = await self._load_status(entity_type, entity_id)
        if status is None:
            raise WorkflowError(
                404,
                f"Entity {entity_type} '{entity_id}' is not registered. "
                "POST it to /workflow/{type}/{id}/register first.",
            )
        return status


def _find_rule_by_action(
    wf: WorkflowDefinition, from_state: str, action: str
) -> Optional[TransitionRule]:
    for rule in wf.transitions_from(from_state):
        if rule.action == action:
            return rule
    return None


def _known_types() -> List[str]:
    from business_twin_ai.workflow.config import all_workflows

    return [wf.entity_type for wf in all_workflows()]
