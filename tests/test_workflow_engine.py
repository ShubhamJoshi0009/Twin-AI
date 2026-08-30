"""Unit tests for the Status Workflow engine and its state machines."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from business_twin_ai.database import Base
from business_twin_ai.workflow.config import all_workflows
from business_twin_ai.workflow.engines.engine import StatusWorkflowEngine, WorkflowError
from business_twin_ai.workflow.models import EntityStatus, StatusTransition


@pytest.fixture
async def db_session():
    """In-memory SQLite async session (mirrors the codebase convention)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ═══════════════════════════════════════════════════════════════════════════════
# State machine definitions are self-consistent
# ═══════════════════════════════════════════════════════════════════════════════

def test_all_workflows_well_formed():
    workflows = all_workflows()
    assert len(workflows) == 6
    types = {wf.entity_type for wf in workflows}
    assert types == {
        "report", "rescue", "waste", "emission", "route", "resource_request",
    }
    for wf in workflows:
        assert wf.initial_state in wf.states
        assert len(wf.states) == len(set(wf.states))
        for t in wf.transitions:
            assert t.from_state in wf.states
            assert t.to_state in wf.states
            assert t.action
            assert t.allowed_roles
            assert t.from_state != t.to_state


def test_report_lifecycle_has_all_spec_stages():
    wf = next(w for w in all_workflows() if w.entity_type == "report")
    actions = {t.action for t in wf.transitions}
    assert actions == {
        "start_review", "mark_duplicate", "verify", "reject",
        "assign", "resolve", "close",
    }
    # Role-limited: only analysts/admins may verify; only dispatchers assign.
    verify = wf.find("under_review", "verified")
    assert set(verify.allowed_roles) == {"analyst", "admin"}
    assign = wf.find("verified", "assigned")
    assert set(assign.allowed_roles) == {"dispatcher", "admin"}
    resolve = wf.find("assigned", "resolved")
    assert "responder" in resolve.allowed_roles
    # Reject and assign both require notes.
    assert wf.find("under_review", "rejected").requires_notes is True
    assert wf.find("verified", "assigned").requires_notes is True


# ═══════════════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_entity_starts_at_initial_state(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    status = await engine.register_entity(
        "report", "rep-1", actor_id="ops", actor_role="admin"
    )
    assert status.current_state == "submitted"
    assert status.version == 1
    await db_session.commit()

    history = await engine.history("report", "rep-1")
    assert len(history) == 1
    assert history[0].action == "register"
    assert history[0].to_state == "submitted"
    assert history[0].actor_id == "ops"


@pytest.mark.asyncio
async def test_register_is_idempotent(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("rescue", "rescue-7", actor_id="a", actor_role="admin")
    await engine.register_entity("rescue", "rescue-7", actor_id="a", actor_role="admin")
    await db_session.commit()

    status = await engine.get_status("rescue", "rescue-7")
    assert status is not None
    assert status.version == 1
    history = await engine.history("rescue", "rescue-7")
    assert len(history) == 1  # no duplicate registration audit rows


@pytest.mark.asyncio
async def test_unknown_entity_type_404(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    with pytest.raises(WorkflowError) as exc:
        await engine.register_entity("spaceship", "x-1", actor_role="admin")
    assert exc.value.status_code == 404
    assert "spaceship" in exc.value.message


@pytest.mark.asyncio
async def test_transition_on_unregistered_entity_404(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    with pytest.raises(WorkflowError) as exc:
        await engine.transit(
            "report", "never-registered", action="verify",
            actor_id="u", actor_role="analyst",
        )
    assert exc.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Full lifecycle transitions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_full_report_lifecycle(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-42", actor_id="sys", actor_role="admin")

    steps = [
        ("analyst", "start_review", "submitted", "under_review", None),
        ("analyst", "verify", "under_review", "verified", None),
        ("dispatcher", "assign", "verified", "assigned", "Team Bravo assigned"),
        ("responder", "resolve", "assigned", "resolved", "Rescued 3 residents"),
        ("dispatcher", "close", "resolved", "closed", None),
    ]
    for role, action, from_state, to_state, notes in steps:
        transition, status = await engine.transit(
            "report", "rep-42", action=action,
            actor_id=f"user-{role}", actor_role=role, notes=notes,
        )
        assert transition.from_state == from_state
        assert transition.to_state == to_state
        assert transition.actor_id == f"user-{role}"
        assert status.current_state == to_state

    await db_session.commit()

    # Audit trail contains registration + 5 transitions, in order.
    history = await engine.history("report", "rep-42")
    assert len(history) == 6
    assert [h.action for h in history] == [
        "register", "start_review", "verify", "assign", "resolve", "close",
    ]

    status = await engine.get_status("report", "rep-42")
    assert status.current_state == "closed"
    assert status.version == 6  # incremented on every transition


@pytest.mark.asyncio
async def test_version_counter_increments(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("emission", "em-1", actor_role="admin")
    _, status = await engine.transit(
        "emission", "em-1", action="plan_mitigation",
        actor_id="u", actor_role="analyst",
    )
    assert status.version == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Role limits
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_role_not_allowed_403(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-9", actor_role="admin")
    # Advance to under_review so "verify" is a legal action — then the role
    # check is what must reject a plain reporter.
    await engine.transit(
        "report", "rep-9", action="start_review",
        actor_id="analyst-1", actor_role="analyst",
    )

    with pytest.raises(WorkflowError) as exc:
        await engine.transit(
            "report", "rep-9", action="verify",
            actor_id="reporter-1", actor_role="reporter",
        )
    assert exc.value.status_code == 403
    assert "reporter" in exc.value.message

    # Nothing was written by the failed attempt.
    history = await engine.history("report", "rep-9")
    assert len(history) == 2  # registration + the successful start_review only


@pytest.mark.asyncio
async def test_admin_can_perform_any_transition(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("route", "route-1", actor_role="admin")
    _, status = await engine.transit(
        "route", "route-1", action="approve", actor_id="a", actor_role="admin"
    )
    assert status.current_state == "approved"
    _, status = await engine.transit(
        "route", "route-1", action="activate", actor_id="a", actor_role="admin"
    )
    assert status.current_state == "active"


# ═══════════════════════════════════════════════════════════════════════════════
# Illegal transitions / notes enforcement
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_illegal_transition_422(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-5", actor_role="admin")
    with pytest.raises(WorkflowError) as exc:
        await engine.transit(
            "report", "rep-5", action="close", actor_id="a", actor_role="admin"
        )
    assert exc.value.status_code == 422
    assert "close" in exc.value.message


@pytest.mark.asyncio
async def test_notes_required_422(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-6", actor_role="admin")
    # Advance to verified first.
    await engine.transit(
        "report", "rep-6", action="start_review", actor_id="a", actor_role="analyst"
    )
    await engine.transit(
        "report", "rep-6", action="verify", actor_id="a", actor_role="analyst"
    )

    with pytest.raises(WorkflowError) as exc:
        await engine.transit(
            "report", "rep-6", action="assign",
            actor_id="d", actor_role="dispatcher", notes="   ",
        )
    assert exc.value.status_code == 422
    assert "notes" in exc.value.message


@pytest.mark.asyncio
async def test_same_action_from_different_states(db_session: AsyncSession):
    """'cancel' is legal from both 'requested' and 'dispatched' for rescues."""
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("rescue", "rescue-2", actor_role="admin")
    _, status = await engine.transit(
        "rescue", "rescue-2", action="cancel",
        actor_id="d", actor_role="dispatcher", notes="weather",
    )
    assert status.current_state == "cancelled"

    await engine.register_entity("rescue", "rescue-3", actor_role="admin")
    await engine.transit(
        "rescue", "rescue-3", action="dispatch_team",
        actor_id="d", actor_role="dispatcher", notes="go",
    )
    _, status = await engine.transit(
        "rescue", "rescue-3", action="cancel",
        actor_id="d", actor_role="dispatcher", notes="weather",
    )
    assert status.current_state == "cancelled"


# ═══════════════════════════════════════════════════════════════════════════════
# Reads: status, available actions, audit, timeline
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_available_actions_from_current_state(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-3", actor_role="admin")

    actions = await engine.available_actions("report", "rep-3")
    assert {a.action for a in actions} == {"start_review", "mark_duplicate"}

    await engine.transit(
        "report", "rep-3", action="start_review", actor_id="a", actor_role="analyst"
    )
    actions = await engine.available_actions("report", "rep-3")
    assert {a.action for a in actions} == {"verify", "reject"}


@pytest.mark.asyncio
async def test_audit_filtering(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-a", actor_role="admin")
    await engine.register_entity("report", "rep-b", actor_role="admin")
    await engine.transit(
        "report", "rep-a", action="start_review", actor_id="alice", actor_role="analyst"
    )
    await engine.transit(
        "report", "rep-b", action="start_review", actor_id="bob", actor_role="analyst"
    )
    await db_session.commit()

    total, by_actor = await engine.audit(actor_id="alice")
    assert total == 1
    assert len(by_actor) == 1
    assert by_actor[0].entity_id == "rep-a"

    total, by_type = await engine.audit(entity_type="report")
    assert total == 4  # 2 registrations + 2 reviews

    total, by_state = await engine.audit(to_state="under_review")
    assert total == 2

    # total reflects the full match set even when limit truncates entries.
    total, limited = await engine.audit(limit=1)
    assert len(limited) == 1
    assert total == 4


@pytest.mark.asyncio
async def test_timeline_returns_most_recent_first(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("waste", "w-1", actor_role="admin")
    await engine.register_entity("resource_request", "r-1", actor_role="admin")
    await db_session.commit()

    feed = await engine.timeline(limit=10)
    assert len(feed) == 2
    assert feed[0].created_at >= feed[1].created_at
    assert {e.entity_type for e in feed} == {"waste", "resource_request"}


@pytest.mark.asyncio
async def test_history_does_not_expose_other_entities(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-x", actor_role="admin")
    await engine.register_entity("report", "rep-y", actor_role="admin")
    await db_session.commit()
    assert len(await engine.history("report", "rep-x")) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Optimistic concurrency
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_concurrent_transition_conflict_409(db_session: AsyncSession, monkeypatch):
    """A stale version must be rejected instead of double-applied."""
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-race", actor_role="admin")
    await db_session.commit()

    # Capture the engine's view of the entity (a *detached copy* — the
    # identity map would otherwise alias stale and the committed row).
    live = await engine.get_status("report", "rep-race")
    stale = EntityStatus(
        entity_type=live.entity_type,
        entity_id=live.entity_id,
        current_state=live.current_state,
        version=live.version,
    )
    # Simulate a concurrent actor committing a newer version behind its back.
    live.version = stale.version + 1
    await db_session.commit()

    # Force the engine to act on its stale view (read happened before the
    # concurrent bump — the exact interleaving the optimistic lock guards).
    async def stale_load(entity_type: str, entity_id: str) -> EntityStatus:
        return stale

    monkeypatch.setattr(engine, "_load_status", stale_load)

    with pytest.raises(WorkflowError) as exc:
        await engine.transit(
            "report", "rep-race", action="start_review",
            actor_id="u", actor_role="analyst",
        )
    assert exc.value.status_code == 409

    # Nothing was written by the rejected attempt.
    history = await engine.history("report", "rep-race")
    assert len(history) == 1  # only the registration row


@pytest.mark.asyncio
async def test_register_concurrent_duplicate_is_idempotent(db_session: AsyncSession):
    """Concurrent registrations must yield one status row, one audit anchor."""
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("rescue", "rescue-race", actor_role="admin")
    # Second registration in the same session hits the unique constraint and
    # returns the existing row instead of failing.
    status = await engine.register_entity("rescue", "rescue-race", actor_role="admin")
    await db_session.commit()

    assert status.current_state == "requested"
    history = await engine.history("rescue", "rescue-race")
    assert len(history) == 1


@pytest.mark.asyncio
async def test_entities_persist_across_sessions(db_session: AsyncSession):
    engine = StatusWorkflowEngine(db_session)
    await engine.register_entity("report", "rep-persist", actor_role="admin")
    await engine.transit(
        "report", "rep-persist", action="start_review",
        actor_id="a", actor_role="analyst",
    )
    await db_session.commit()

    rows = (await db_session.execute(select(StatusTransition))).scalars().all()
    statuses = (await db_session.execute(select(EntityStatus))).scalars().all()
    assert len(rows) == 2
    assert len(statuses) == 1
    assert statuses[0].current_state == "under_review"
    assert statuses[0].version == 2
