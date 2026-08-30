"""Register all supply chain API routers."""

from __future__ import annotations

from fastapi import APIRouter

from business_twin_ai.supply_chain.api.routes import (
    agent,
    alerts,
    health,
    inventory,
    logistics,
    optimization,
    reports,
    risk,
    routes,
    scenario,
    supplier,
    warehouse,
    weather,
)


def register_supply_chain_routes(parent_router: APIRouter) -> None:
    """Include all supply chain route modules."""
    sc_router = APIRouter(prefix="/api/v1/supply-chain", tags=["Supply Chain"])

    sc_router.include_router(supplier.router, prefix="/suppliers")
    sc_router.include_router(warehouse.router, prefix="/warehouses")
    sc_router.include_router(inventory.router, prefix="/inventory")
    sc_router.include_router(logistics.router, prefix="/shipments")
    sc_router.include_router(risk.router, prefix="/risks")
    sc_router.include_router(alerts.router, prefix="/alerts")
    sc_router.include_router(agent.router, prefix="/agent")
    sc_router.include_router(health.router, prefix="/health")
    sc_router.include_router(optimization.router, prefix="/optimization")
    sc_router.include_router(scenario.router, prefix="/scenarios")
    sc_router.include_router(reports.router, prefix="/reports")
    sc_router.include_router(routes.router, prefix="/routes")
    sc_router.include_router(weather.router, prefix="/routes")

    parent_router.include_router(sc_router)
