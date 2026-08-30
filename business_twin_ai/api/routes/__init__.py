"""Register all API routers on the main FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from business_twin_ai.api.routes import (
    agent,
    agentic,
    digital_twin,
    health,
    insights,
    market,
    news,
    report,
    simulation,
    strategy,
    system,
    timeline,
)


def register_routes(app: FastAPI) -> None:
    """Include all route modules under the /api/v1 prefix."""
    prefix = "/api/v1"

    app.include_router(digital_twin.router, prefix=prefix)
    app.include_router(simulation.router, prefix=prefix)
    app.include_router(health.router, prefix=prefix)
    app.include_router(strategy.router, prefix=prefix)
    app.include_router(agent.router, prefix=prefix)
    app.include_router(insights.router, prefix=prefix)
    app.include_router(report.router, prefix=prefix)
    app.include_router(timeline.router, prefix=prefix)
    app.include_router(system.router, prefix=prefix)
    app.include_router(news.router, prefix=prefix)
    app.include_router(agentic.router, prefix=prefix)
    app.include_router(market.router, prefix=prefix)
