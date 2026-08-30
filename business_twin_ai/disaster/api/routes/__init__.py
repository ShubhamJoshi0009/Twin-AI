"""Register all disaster API routers on the FastAPI app."""

from __future__ import annotations

from fastapi import FastAPI

from business_twin_ai.disaster.api.routes import clusters, map, reports


def register_disaster_routes(app: FastAPI) -> None:
    """Include disaster report endpoints under ``/api/v1/disaster``.

    The relative paths mirror the spec (§14): /validate-report, /report/{id}/validation,
    /reports/duplicates, /reports/suspicious, /clusters, /clusters/{cluster_id},
    /map/warnings — all prefixed with ``/api/v1/disaster`` so existing endpoints
    under ``/api/v1`` (e.g. the business report generator) stay untouched.
    """
    prefix = "/api/v1/disaster"
    app.include_router(reports.router, prefix=prefix, tags=["Disaster Reports"])
    app.include_router(clusters.router, prefix=prefix, tags=["Disaster Clusters"])
    app.include_router(map.router, prefix=prefix, tags=["Disaster Map"])
