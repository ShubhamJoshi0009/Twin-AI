"""Status workflow configuration: roles, states and transition rules.

Every entity type (reports, rescues, waste, emissions, routes, resource
requests) gets an explicit lifecycle. Transitions declare which roles may
perform them, so update actions are role-limited. All rules live here so new
entity types or policy changes never require touching engine code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# ── Roles ─────────────────────────────────────────────────────────────────────
# In production these would come from an authenticated session / JWT. The API
# accepts `actor_role` explicitly so the workflow layer stays pluggable.
ROLE_ADMIN = "admin"
ROLE_DISPATCHER = "dispatcher"
ROLE_ANALYST = "analyst"
ROLE_RESPONDER = "responder"
ROLE_REPORTER = "reporter"

ALL_ROLES: Tuple[str, ...] = (
    ROLE_ADMIN,
    ROLE_DISPATCHER,
    ROLE_ANALYST,
    ROLE_RESPONDER,
    ROLE_REPORTER,
)

@dataclass(frozen=True)
class TransitionRule:
    """One allowed lifecycle edge: from_state → to_state, with role limits."""

    from_state: str
    to_state: str
    action: str
    allowed_roles: Tuple[str, ...]
    requires_notes: bool = False
    description: str = ""


@dataclass(frozen=True)
class WorkflowDefinition:
    """A complete lifecycle for one entity type."""

    entity_type: str
    label: str
    initial_state: str
    states: Tuple[str, ...]
    transitions: Tuple[TransitionRule, ...]
    description: str = ""

    def transitions_from(self, state: str) -> List[TransitionRule]:
        return [t for t in self.transitions if t.from_state == state]

    def find(self, from_state: str, to_state: str) -> TransitionRule | None:
        for t in self.transitions:
            if t.from_state == from_state and t.to_state == to_state:
                return t
        return None


# ── Lifecycle definitions per entity type ────────────────────────────────────

_WORKFLOWS: List[WorkflowDefinition] = [
    # ── Reports (disaster / emergency reports) ──
    WorkflowDefinition(
        entity_type="report",
        label="Disaster / Emergency Report",
        initial_state="submitted",
        description="Lifecycle of a disaster or emergency report from submission to closure.",
        states=(
            "submitted", "under_review", "verified", "assigned",
            "resolved", "closed", "rejected", "duplicate",
        ),
        transitions=(
            TransitionRule(
                "submitted", "under_review", "start_review",
                (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "submitted", "duplicate", "mark_duplicate",
                (ROLE_ANALYST, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "under_review", "verified", "verify", (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "under_review", "rejected", "reject",
                (ROLE_ANALYST, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "verified", "assigned", "assign",
                (ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "assigned", "resolved", "resolve",
                (ROLE_RESPONDER, ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "resolved", "closed", "close", (ROLE_DISPATCHER, ROLE_ADMIN),
            ),
        ),
    ),
    # ── Rescues ──
    WorkflowDefinition(
        entity_type="rescue",
        label="Rescue Operation",
        initial_state="requested",
        states=("requested", "dispatched", "on_site", "completed", "closed", "cancelled"),
        transitions=(
            TransitionRule(
                "requested", "dispatched", "dispatch_team",
                (ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "dispatched", "on_site", "arrive",
                (ROLE_RESPONDER, ROLE_DISPATCHER),
            ),
            TransitionRule(
                "on_site", "completed", "complete",
                (ROLE_RESPONDER, ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "completed", "closed", "close", (ROLE_ADMIN, ROLE_DISPATCHER),
            ),
            TransitionRule(
                "requested", "cancelled", "cancel",
                (ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "dispatched", "cancelled", "cancel",
                (ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
        ),
    ),
    # ── Waste management requests ──
    WorkflowDefinition(
        entity_type="waste",
        label="Waste Management Request",
        initial_state="reported",
        states=("reported", "scheduled", "collected", "disposed", "closed"),
        transitions=(
            TransitionRule(
                "reported", "scheduled", "schedule_collection",
                (ROLE_DISPATCHER, ROLE_ADMIN),
            ),
            TransitionRule(
                "scheduled", "collected", "mark_collected",
                (ROLE_RESPONDER, ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "collected", "disposed", "mark_disposed",
                (ROLE_RESPONDER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "disposed", "closed", "close", (ROLE_ADMIN, ROLE_DISPATCHER),
            ),
        ),
    ),
    # ── Emissions control tasks ──
    WorkflowDefinition(
        entity_type="emission",
        label="Emissions Control Task",
        initial_state="identified",
        states=("identified", "planned", "implemented", "verified", "closed"),
        transitions=(
            TransitionRule(
                "identified", "planned", "plan_mitigation",
                (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "planned", "implemented", "implement",
                (ROLE_RESPONDER, ROLE_ANALYST, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "implemented", "verified", "verify", (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "verified", "closed", "close", (ROLE_ADMIN, ROLE_ANALYST),
            ),
        ),
    ),
    # ── Routes (diversions / logistics) ──
    WorkflowDefinition(
        entity_type="route",
        label="Route / Diversion",
        initial_state="proposed",
        states=("proposed", "approved", "active", "reverted", "closed", "rejected"),
        transitions=(
            TransitionRule(
                "proposed", "approved", "approve", (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "proposed", "rejected", "reject",
                (ROLE_ANALYST, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "approved", "active", "activate", (ROLE_DISPATCHER, ROLE_ADMIN),
            ),
            TransitionRule(
                "active", "reverted", "revert",
                (ROLE_DISPATCHER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "reverted", "closed", "close", (ROLE_ADMIN, ROLE_DISPATCHER),
            ),
        ),
    ),
    # ── Resource requests ──
    WorkflowDefinition(
        entity_type="resource_request",
        label="Resource Request",
        initial_state="requested",
        states=("requested", "reviewed", "approved", "fulfilled", "closed", "rejected"),
        transitions=(
            TransitionRule(
                "requested", "reviewed", "start_review",
                (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "reviewed", "approved", "approve", (ROLE_ANALYST, ROLE_ADMIN),
            ),
            TransitionRule(
                "reviewed", "rejected", "reject",
                (ROLE_ANALYST, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "approved", "fulfilled", "fulfill",
                (ROLE_DISPATCHER, ROLE_RESPONDER, ROLE_ADMIN), requires_notes=True,
            ),
            TransitionRule(
                "fulfilled", "closed", "close", (ROLE_ADMIN, ROLE_DISPATCHER),
            ),
        ),
    ),
]

WORKFLOWS_BY_TYPE: Dict[str, WorkflowDefinition] = {
    wf.entity_type: wf for wf in _WORKFLOWS
}


def get_workflow(entity_type: str) -> WorkflowDefinition | None:
    return WORKFLOWS_BY_TYPE.get(entity_type)


def all_workflows() -> Tuple[WorkflowDefinition, ...]:
    return tuple(_WORKFLOWS)
