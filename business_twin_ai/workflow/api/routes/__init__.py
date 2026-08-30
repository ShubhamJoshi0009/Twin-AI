"""Register all status workflow API routers on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from business_twin_ai.workflow.api.routes import workflows


def register_workflow_routes(app: FastAPI) -> None:
    """Include workflow endpoints under ``/api/v1/workflow``."""
    app.include_router(workflows.router, prefix="/api/v1/workflow", tags=["Status Workflow"])
