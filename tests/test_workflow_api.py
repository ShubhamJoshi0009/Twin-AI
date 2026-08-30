"""API integration tests for the Status Workflow endpoints.

Runs against the real FastAPI app over ASGI. The shared SQLite test DB is
used, so each test cleans up the workflow tables it creates.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from business_twin_ai.app import app  # noqa: E402
from business_twin_ai.database import Base  # noqa: E402

WORKFLOW = "/api/v1/workflow"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def clean_workflow_tables():
    """Ensure a pristine workflow dataset + fresh schema before each test.

    Drop + recreate the two workflow tables so schema changes (e.g. nullable
    columns) never linger in the shared SQLite test file across runs.
    """
    from sqlalchemy import delete

    from business_twin_ai.database import async_session_factory, engine

    # Recreate the workflow tables with the *current* model definitions.
    async with engine.begin() as conn:
        from business_twin_ai.workflow.models import EntityStatus, StatusTransition

        await conn.run_sync(
            Base.metadata.drop_all,
            tables=[StatusTransition.__table__, EntityStatus.__table__],
        )
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[StatusTransition.__table__, EntityStatus.__table__],
        )
    yield
    async with async_session_factory() as session:
        await session.execute(delete(StatusTransition))
        await session.execute(delete(EntityStatus))
        await session.commit()


async def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def transition_body(action: str, role: str, actor: str = "user-1", notes=None) -> dict:
    body = {"action": action, "actor_id": actor, "actor_role": role}
    if notes is not None:
        body["notes"] = notes
    return body


# ═══════════════════════════════════════════════════════════════════════════════
# Registration + full lifecycle via the API
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_entity_via_api():
    async with await client() as c:
        r = await c.post(
            f"{WORKFLOW}/report/rep-100/register",
            json={"actor_id": "ops", "actor_role": "admin", "notes": "initial intake"},
        )
    assert r.status_code == 201
    body = r.json()
    assert body["entity_type"] == "report"
    assert body["entity_id"] == "rep-100"
    assert body["current_state"] == "submitted"
    assert body["version"] == 1
    actions = {a["action"] for a in body["available_actions"]}
    assert actions == {"start_review", "mark_duplicate"}


@pytest.mark.asyncio
async def test_full_report_lifecycle_via_api():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-101/register",
            json={"actor_id": "ops", "actor_role": "admin"},
        )

        # analyst starts review
        r = await c.post(
            f"{WORKFLOW}/report/rep-101/transitions",
            json=transition_body("start_review", "analyst"),
        )
        assert r.status_code == 200
        assert r.json()["status"]["current_state"] == "under_review"
        assert r.json()["transition"]["actor_role"] == "analyst"

        # analyst verifies
        await c.post(
            f"{WORKFLOW}/report/rep-101/transitions",
            json=transition_body("verify", "analyst"),
        )

        # dispatcher assigns (notes required)
        r = await c.post(
            f"{WORKFLOW}/report/rep-101/transitions",
            json=transition_body("assign", "dispatcher", notes="Team Bravo assigned"),
        )
        assert r.json()["status"]["current_state"] == "assigned"

        # responder resolves
        r = await c.post(
            f"{WORKFLOW}/report/rep-101/transitions",
            json=transition_body("resolve", "responder", notes="Rescued 3 residents"),
        )
        assert r.json()["status"]["current_state"] == "resolved"

        # dispatcher closes
        r = await c.post(
            f"{WORKFLOW}/report/rep-101/transitions",
            json=transition_body("close", "dispatcher"),
        )
        assert r.json()["status"]["current_state"] == "closed"

        # history: 1 registration + 5 transitions, oldest first
        h = await c.get(f"{WORKFLOW}/report/rep-101/history")
        assert h.status_code == 200
        entries = h.json()
        assert [e["action"] for e in entries] == [
            "register", "start_review", "verify", "assign", "resolve", "close",
        ]
        assert entries[0]["to_state"] == "submitted"
        assert all("actor_id" in e and "created_at" in e for e in entries)

        # status endpoint now shows no available actions (closed is terminal)
        s = await c.get(f"{WORKFLOW}/report/rep-101/status")
        assert s.json()["current_state"] == "closed"
        assert s.json()["available_actions"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Role limits → 403
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_role_not_allowed_403():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-200/register",
            json={"actor_id": "ops", "actor_role": "admin"},
        )
        # Advance to under_review so "verify" is legal — then the role check
        # is what must reject a plain reporter.
        await c.post(
            f"{WORKFLOW}/report/rep-200/transitions",
            json=transition_body("start_review", "analyst"),
        )
        r = await c.post(
            f"{WORKFLOW}/report/rep-200/transitions",
            json=transition_body("verify", "reporter"),
        )
    assert r.status_code == 403
    assert "reporter" in r.json()["detail"]

    # Nothing recorded for the rejected attempt.
    async with await client() as c:
        h = await c.get(f"{WORKFLOW}/report/rep-200/history")
    assert len(h.json()) == 2  # register + start_review only


@pytest.mark.asyncio
async def test_dispatcher_cannot_verify():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-201/register",
            json={"actor_id": "ops", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/report/rep-201/transitions",
            json=transition_body("start_review", "analyst"),
        )
        r = await c.post(
            f"{WORKFLOW}/report/rep-201/transitions",
            json=transition_body("verify", "dispatcher"),
        )
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Error cases: 404 / 422
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_unknown_entity_type_404():
    async with await client() as c:
        r = await c.post(
            f"{WORKFLOW}/spaceship/x/register",
            json={"actor_id": "a", "actor_role": "admin"},
        )
    assert r.status_code == 404
    assert "spaceship" in r.json()["detail"]


@pytest.mark.asyncio
async def test_unregistered_entity_404():
    async with await client() as c:
        r = await c.post(
            f"{WORKFLOW}/report/ghost/transitions",
            json=transition_body("verify", "analyst"),
        )
        assert r.status_code == 404

        s = await c.get(f"{WORKFLOW}/report/ghost/status")
        assert s.status_code == 404


@pytest.mark.asyncio
async def test_illegal_transition_422():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-300/register",
            json={"actor_id": "ops", "actor_role": "admin"},
        )
        r = await c.post(
            f"{WORKFLOW}/report/rep-300/transitions",
            json=transition_body("close", "admin"),  # cannot close straight from submitted
        )
    assert r.status_code == 422
    assert "close" in r.json()["detail"]


@pytest.mark.asyncio
async def test_missing_notes_422():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-301/register",
            json={"actor_id": "ops", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/report/rep-301/transitions",
            json=transition_body("start_review", "analyst"),
        )
        await c.post(
            f"{WORKFLOW}/report/rep-301/transitions",
            json=transition_body("verify", "analyst"),
        )
        r = await c.post(
            f"{WORKFLOW}/report/rep-301/transitions",
            json=transition_body("assign", "dispatcher", notes=""),
        )
    assert r.status_code == 422
    assert "notes" in r.json()["detail"]


@pytest.mark.asyncio
async def test_unknown_role_rejected_by_schema():
    async with await client() as c:
        r = await c.post(
            f"{WORKFLOW}/report/rep-302/register",
            json={"actor_id": "a", "actor_role": "superhero"},
        )
    assert r.status_code == 422  # pydantic validation error


# ═══════════════════════════════════════════════════════════════════════════════
# Global views: definitions, audit, timeline
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_definitions_endpoint():
    async with await client() as c:
        r = await c.get(f"{WORKFLOW}/definitions")
    assert r.status_code == 200
    workflows = r.json()["workflows"]
    assert len(workflows) == 6
    by_type = {w["entity_type"]: w for w in workflows}
    report = by_type["report"]
    assert report["initial_state"] == "submitted"
    assert "resolved" in report["states"]
    verify = next(t for t in report["transitions"] if t["action"] == "verify")
    assert set(verify["allowed_roles"]) == {"analyst", "admin"}


@pytest.mark.asyncio
async def test_audit_endpoint_filters():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-400/register",
            json={"actor_id": "alice", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/rescue/rescue-400/register",
            json={"actor_id": "bob", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/report/rep-400/transitions",
            json=transition_body("start_review", "analyst", actor="alice"),
        )

        all_entries = await c.get(f"{WORKFLOW}/audit")
        assert all_entries.status_code == 200
        assert all_entries.json()["total"] == 3

        by_actor = await c.get(f"{WORKFLOW}/audit", params={"actor_id": "bob"})
        assert by_actor.json()["total"] == 1
        assert by_actor.json()["entries"][0]["entity_type"] == "rescue"

        by_type = await c.get(f"{WORKFLOW}/audit", params={"entity_type": "report"})
        assert by_type.json()["total"] == 2

        to_state = await c.get(f"{WORKFLOW}/audit", params={"to_state": "under_review"})
        assert to_state.json()["total"] == 1

        limited = await c.get(f"{WORKFLOW}/audit", params={"limit": 1})
        # total is the true match count; limit truncates the entries.
        assert limited.json()["total"] == 3
        assert len(limited.json()["entries"]) == 1


@pytest.mark.asyncio
async def test_dashboard_timeline_endpoint():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/waste/w-1/register",
            json={"actor_id": "a", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/waste/w-1/transitions",
            json=transition_body("schedule_collection", "dispatcher"),
        )
        await c.post(
            f"{WORKFLOW}/waste/w-1/transitions",
            json=transition_body("mark_collected", "responder", notes="Bin emptied"),
        )
        r = await c.get(f"{WORKFLOW}/timeline")
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) == 3
    # Newest first
    assert entries[0]["action"] == "mark_collected"
    assert entries[0]["entity_type"] == "waste"
    assert entries[-1]["action"] == "register"


@pytest.mark.asyncio
async def test_dashboard_timeline_cross_entity():
    async with await client() as c:
        await c.post(
            f"{WORKFLOW}/report/rep-500/register",
            json={"actor_id": "a", "actor_role": "admin"},
        )
        await c.post(
            f"{WORKFLOW}/emission/em-500/register",
            json={"actor_id": "b", "actor_role": "admin"},
        )
        r = await c.get(f"{WORKFLOW}/timeline", params={"limit": 5})
    assert r.status_code == 200
    types = {e["entity_type"] for e in r.json()}
    assert types == {"report", "emission"}


# ═══════════════════════════════════════════════════════════════════════════════
# Idempotent registration via API
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_register_twice_is_idempotent():
    async with await client() as c:
        body = {"actor_id": "ops", "actor_role": "admin"}
        await c.post(f"{WORKFLOW}/rescue/rescue-1/register", json=body)
        r2 = await c.post(f"{WORKFLOW}/rescue/rescue-1/register", json=body)
        h = await c.get(f"{WORKFLOW}/rescue/rescue-1/history")
    assert r2.status_code == 201
    assert r2.json()["version"] == 1  # not bumped by re-registration
    assert len(h.json()) == 1
