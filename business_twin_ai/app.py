"""Business Twin AI — Main FastAPI Application.

Run with:
    uvicorn business_twin_ai.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from business_twin_ai.api.routes import register_routes
from business_twin_ai.config import settings
from business_twin_ai.database import async_session_factory, init_db
from business_twin_ai.disaster.api.routes import register_disaster_routes
from business_twin_ai.disaster.middleware import ValidationMiddleware
from business_twin_ai.supply_chain.api.routes import register_supply_chain_routes
from business_twin_ai.workflow.api.routes import register_workflow_routes

logger = logging.getLogger(__name__)


async def _profile_audit_loop() -> None:
    """Scheduled auto-verify: periodically re-audit every profile's sources.

    Runs shortly after startup, then every ``PROFILE_AUDIT_INTERVAL_SECONDS``
    (0 disables the loop). Logs coverage / verified-section regressions and
    refreshes the audit snapshots. Never raises — the loop survives failures.
    """
    from business_twin_ai.core.engines.source_checklist import SourceChecklistEngine

    interval = settings.PROFILE_AUDIT_INTERVAL_SECONDS
    await asyncio.sleep(min(30, max(5, interval // 10)))
    while True:
        try:
            async with async_session_factory() as session:
                summary = await SourceChecklistEngine(session).audit_all()
                await session.commit()
            logger.info("Scheduled profile audit complete: %s", summary)
        except Exception as exc:  # noqa: BLE001 — never let the loop die
            logger.warning("Scheduled profile audit failed: %s", exc)
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    # Startup: create tables, then seed demo data if the DB is empty.
    await init_db()
    if settings.AUTO_SEED_DEMO:
        from business_twin_ai.seed import seed_database

        try:
            async with async_session_factory() as session:
                summary = await seed_database(session)
                await session.commit()
            if not summary.get("skipped"):
                logger.info("Seeded demo dataset: %s", summary)
        except Exception as exc:  # noqa: BLE001 — never block startup on seed errors
            logger.warning("Demo seed skipped (startup continues): %s", exc)

    # Background source re-audit (scheduled auto-verify).
    audit_task: asyncio.Task | None = None
    if settings.PROFILE_AUDIT_INTERVAL_SECONDS > 0:
        audit_task = asyncio.create_task(_profile_audit_loop())
        logger.info(
            "Profile source auto-verify scheduled every %ss",
            settings.PROFILE_AUDIT_INTERVAL_SECONDS,
        )
    yield
    # Shutdown: stop the background audit loop.
    if audit_task is not None:
        audit_task.cancel()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Enterprise Digital Twin & Business Decision AI Engine. "
        "Create digital twins, simulate business decisions, predict outcomes, "
        "generate strategies, and get AI-powered recommendations."
    ),
    # Swagger/OpenAPI docs are only exposed in debug mode (development).
    docs_url="/docs" if settings.APP_DEBUG else None,
    redoc_url="/redoc" if settings.APP_DEBUG else None,
    openapi_url="/openapi.json" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

# ── Trusted hosts (production hardening) ────────────────────────────────────
# When TRUSTED_HOSTS is set, requests with an unexpected Host header are
# rejected (blocks DNS-rebinding / Host-header poisoning attacks).
if settings.trusted_hosts_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts_list)
    logger.info("TrustedHostMiddleware enabled for hosts: %s", settings.trusted_hosts_list)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────────────
register_routes(app)
register_supply_chain_routes(app)
register_disaster_routes(app)
register_workflow_routes(app)

# ── Disaster report validation middleware ───────────────────────────────────
# Every report-creation API flows through ValidationMiddleware → ValidationService
# → Store (spec §11). Existing endpoints are untouched — only report creation
# paths are intercepted.
app.add_middleware(ValidationMiddleware)


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": ("/docs" if settings.APP_DEBUG else None),
        "api_base": "/api/v1",
        "endpoints": {
            "digital_twins": "/api/v1/digital-twins",
            "simulations": "/api/v1/simulations",
            "health": "/api/v1/health",
            "strategies": "/api/v1/strategies",
            "agent": "/api/v1/agent",
            "insights": "/api/v1/insights",
            "reports": "/api/v1/reports",
            "timeline": "/api/v1/timeline",
            "supply_chain": "/api/v1/supply-chain",
            "disaster_reports": "/api/v1/disaster",
            "status_workflow": "/api/v1/workflow",
        },
    }
