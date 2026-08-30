"""API routes for the Route Diversion Simulator (world map)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from business_twin_ai.services.news.gdelt import fetch_market_news
from business_twin_ai.supply_chain.engines.discovery import discover_route_scenarios
from business_twin_ai.supply_chain.engines.routes import (
    CHOKEPOINTS,
    EVENT_TYPES,
    PORT_COORDS,
    RouteDiversionEngine,
)
from business_twin_ai.supply_chain.schemas.schemas import RouteRiskResponse

router = APIRouter()


class RouteSimulateRequest(BaseModel):
    """Simulate a journey and apply chokepoint blockages."""

    origin: str = Field(..., description="Origin port id (see GET /routes/network)")
    destination: str = Field(..., description="Destination port id")
    blocked_chokepoints: List[str] = Field(
        default_factory=list,
        description="Chokepoint ids to block (suez_canal, strait_of_hormuz, malacca_strait, panama_canal, red_sea, bab_el_mandeb, gulf_of_aden)",
    )
    event_type: str = Field(
        default="war_conflict",
        description="One of: war_conflict, piracy, natural_disaster, sanctions, congestion, grounding",
    )
    cargo_value: float = Field(default=1_000_000.0, ge=0, description="Cargo value in USD for cost impact")
    include_news: bool = Field(default=True, description="Fetch real-time news for the affected region")


class Port(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    region: str


class Segment(BaseModel):
    id: str
    from_: str = Field(..., alias="from")
    to: str
    label: str
    chokepoint: Optional[str]
    distance_km: float


class Chokepoint(BaseModel):
    id: str
    name: str
    region: str
    description: str
    severity: str
    risk_multiplier: float
    # Land vs water blockade kind + recommended optimal alternative route.
    kind: str = "maritime"
    solution: str = ""


class RouteNetworkResponse(BaseModel):
    ports: List[Port]
    segments: List[Segment]
    chokepoints: List[Chokepoint]


@router.get("/network", response_model=RouteNetworkResponse)
async def get_route_network() -> RouteNetworkResponse:
    """Return the world shipping network for the map UI."""
    engine = RouteDiversionEngine()
    net = engine.network()
    return RouteNetworkResponse(**net)


@router.get("/event-types")
async def get_event_types() -> dict:
    """List all blockage event types."""
    return {"events": [{"id": k, **v} for k, v in EVENT_TYPES.items()]}


@router.get("/risk-scenarios", response_model=RouteRiskResponse)
async def get_risk_scenarios(
    limit: int = Query(6, ge=1, le=10),
) -> RouteRiskResponse:
    """Live trade-route risk radar — news-driven scenarios per chokepoint.

    Scans today's headlines (NewsAPI.org when configured, else GDELT/curated)
    for each maritime chokepoint and returns ranked scenarios that can be
    applied to the Route Diversion simulator with one click.
    """
    return RouteRiskResponse(**await discover_route_scenarios(limit=limit))


@router.post("/simulate")
async def simulate_route(req: RouteSimulateRequest) -> Dict[str, Any]:
    """Simulate a voyage and compute the diversion impact for blockages."""
    engine = RouteDiversionEngine()
    unknown = [cp for cp in req.blocked_chokepoints if cp not in CHOKEPOINTS]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown chokepoint(s): {', '.join(unknown)}. Valid: {sorted(CHOKEPOINTS)}",
        )

    try:
        result = engine.simulate(
            origin=req.origin,
            destination=req.destination,
            blocked_chokepoints=req.blocked_chokepoints,
            event_type=req.event_type,
            cargo_value=req.cargo_value,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if req.include_news:
        region = ", ".join(c["name"] for c in result["blocked_chokepoints"]) or result["origin"]["region"]
        try:
            articles = await fetch_market_news(f"{region} shipping disruption", limit=4)
            result["news"] = articles
        except Exception:  # noqa: BLE001
            result["news"] = []
    else:
        result["news"] = []

    return result


@router.get("/ports")
async def list_ports() -> List[Dict[str, Any]]:
    """Return the list of routable ports (for dropdowns)."""
    return [
        {"id": pid, "name": meta["name"], "region": meta["region"]}
        for pid, meta in PORT_COORDS.items()
    ]
