"""Real-time weather monitoring for supply routes.

* ``GET /routes/weather`` — current weather at every port + per-lane risk,
  ready to overlay on the world map (with alerts for ORANGE/RED locations).
* ``GET /routes/weather/route`` — weather + aggregated risk along a specific
  voyage (ports on the baseline shortest path), with an actionable summary.

Both are backed by the free Open-Meteo provider with a simulated fallback, so
they always return data — ``mode`` tells the UI whether it is live or
simulated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from business_twin_ai.services.weather.open_meteo import fetch_weather_batch
from business_twin_ai.services.weather.risk import (
    conditions_risk,
    route_weather_risk,
    worst_level,
)
from business_twin_ai.supply_chain.engines.routes import (
    LANES,
    PORT_COORDS,
    RouteDiversionEngine,
)

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class WeatherConditionsOut(BaseModel):
    temperature_c: float
    apparent_temperature_c: float
    wind_speed_kmh: float
    wind_gusts_kmh: float
    precipitation_mm: float
    relative_humidity: float
    weather_code: int
    weather_label: str
    weather_icon: str
    is_day: bool
    observed_at: str
    source: str  # "live" | "simulated"


class PortWeatherOut(BaseModel):
    port_id: str
    name: str
    lat: float
    lng: float
    region: str
    conditions: WeatherConditionsOut
    risk_score: float
    risk_level: str
    summary: str


class LaneWeatherOut(BaseModel):
    model_config = {"populate_by_name": True}

    from_: str = Field(..., alias="from")
    to: str
    lane: str
    chokepoint: Optional[str] = None
    risk_score: float
    risk_level: str


class WeatherAlertOut(BaseModel):
    location: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    level: str
    risk_score: float
    summary: str


class RouteWeatherResponse(BaseModel):
    mode: str  # "live" | "simulated"
    generated_at: datetime
    ports: List[PortWeatherOut]
    lanes: List[LaneWeatherOut]
    alerts: List[WeatherAlertOut]
    summary: Dict[str, Any]


class RouteWeatherPointOut(BaseModel):
    label: str
    lat: float
    lng: float
    risk_score: float
    risk_level: str
    summary: str
    conditions: WeatherConditionsOut


class RouteWeatherDetail(BaseModel):
    mode: str
    generated_at: datetime
    origin: str
    destination: str
    overall_risk_score: float
    overall_level: str
    points: List[RouteWeatherPointOut]
    alerts: List[WeatherAlertOut]
    recommendation: str


# ── Shared helpers ────────────────────────────────────────────────────────────

def _mode_of(conditions_list: List[Dict[str, Any]]) -> str:
    """live if any conditions came from the provider, else simulated."""
    if any(c.get("source") == "live" for c in conditions_list):
        return "live"
    return "simulated"


async def _fetch_port_conditions(port_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Weather conditions for a list of port ids, keyed by port id."""
    points = [
        (PORT_COORDS[pid]["lat"], PORT_COORDS[pid]["lng"])
        for pid in port_ids
        if pid in PORT_COORDS
    ]
    batch = await fetch_weather_batch(points)
    out: Dict[str, Dict[str, Any]] = {}
    for pid in port_ids:
        if pid not in PORT_COORDS:
            continue
        lat, lng = PORT_COORDS[pid]["lat"], PORT_COORDS[pid]["lng"]
        # Match by rounded coordinate (same rounding as the client cache key).
        rounded = (round(lat, 2), round(lng, 2))
        conditions = batch.get(rounded) or {}
        out[pid] = conditions
    return out


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/weather", response_model=RouteWeatherResponse)
async def get_route_weather() -> RouteWeatherResponse:
    """Current weather at every port + per-lane risk for the map overlay."""
    port_ids = list(PORT_COORDS.keys())
    conditions_by_port = await _fetch_port_conditions(port_ids)

    ports_out: List[PortWeatherOut] = []
    alerts: List[WeatherAlertOut] = []
    all_conditions: List[Dict[str, Any]] = []
    for pid in port_ids:
        meta = PORT_COORDS[pid]
        conditions = conditions_by_port[pid]  # always present (simulated fallback)
        all_conditions.append(conditions)
        risk = conditions_risk(conditions)
        ports_out.append(PortWeatherOut(
            port_id=pid,
            name=meta["name"],
            lat=meta["lat"],
            lng=meta["lng"],
            region=meta["region"],
            conditions=WeatherConditionsOut(**conditions),
            risk_score=risk["risk_score"],
            risk_level=risk["level"],
            summary=risk["summary"],
        ))
        if risk["level"] in ("ORANGE", "RED"):
            alerts.append(WeatherAlertOut(
                location=meta["name"],
                lat=meta["lat"],
                lng=meta["lng"],
                level=risk["level"],
                risk_score=risk["risk_score"],
                summary=risk["summary"],
            ))

    # Per-lane risk = worst of its two endpoint ports (cheap, no extra fetch).
    lane_out: List[LaneWeatherOut] = []
    seen = set()
    for entry in LANES:
        a, b, lane, chokepoint = entry[:4]
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        ra = conditions_risk(conditions_by_port[a])
        rb = conditions_risk(conditions_by_port[b])
        score = max(ra["risk_score"], rb["risk_score"])
        lane_out.append(LaneWeatherOut(
            from_=a,
            to=b,
            lane=lane,
            chokepoint=chokepoint,
            risk_score=round(score, 1),
            risk_level=worst_level(ra["level"], rb["level"]),
        ))

    alert_levels = [a.level for a in alerts]
    return RouteWeatherResponse(
        mode=_mode_of(all_conditions),
        generated_at=datetime.now(timezone.utc),
        ports=ports_out,
        lanes=lane_out,
        alerts=alerts,
        summary={
            "ports": len(ports_out),
            "lanes": len(lane_out),
            "alerts": len(alerts),
            "worst_level": worst_level(*alert_levels) if alert_levels else "GREEN",
        },
    )


@router.get("/weather/route", response_model=RouteWeatherDetail)
async def get_route_weather_detail(
    origin: str = Query(..., description="Origin port id"),
    destination: str = Query(..., description="Destination port id"),
) -> RouteWeatherDetail:
    """Weather + aggregated risk along the baseline route between two ports."""
    if origin not in PORT_COORDS or destination not in PORT_COORDS:
        valid = ", ".join(sorted(PORT_COORDS))
        raise HTTPException(status_code=422, detail=f"Unknown port. Valid ports: {valid}")
    if origin == destination:
        raise HTTPException(
            status_code=422, detail="Origin and destination must be different ports"
        )

    engine = RouteDiversionEngine()
    baseline = engine.shortest_path(origin, destination, None)
    if baseline.empty:
        raise HTTPException(status_code=422, detail="No route found between these ports")

    port_ids = _route_port_ids(baseline)
    conditions_by_port = await _fetch_port_conditions(port_ids)

    points: List[Dict[str, Any]] = []
    for pid in port_ids:
        meta = PORT_COORDS[pid]
        points.append({
            "label": meta["name"],
            "lat": meta["lat"],
            "lng": meta["lng"],
            "conditions": conditions_by_port[pid],
        })

    assessment = route_weather_risk(points)
    recommendation = _recommendation(assessment, origin, destination)
    all_conditions = [p["conditions"] for p in points]

    return RouteWeatherDetail(
        mode=_mode_of(all_conditions),
        generated_at=datetime.now(timezone.utc),
        origin=origin,
        destination=destination,
        overall_risk_score=assessment["risk_score"],
        overall_level=assessment["level"],
        points=[
            RouteWeatherPointOut(
                label=p["label"],
                lat=p["lat"],
                lng=p["lng"],
                risk_score=p["risk_score"],
                risk_level=p["level"],
                summary=p["summary"],
                conditions=WeatherConditionsOut(**p["conditions"]),
            )
            for p in assessment["points"]
        ],
        alerts=[WeatherAlertOut(**a) for a in assessment["alerts"]],
        recommendation=recommendation,
    )


def _route_port_ids(baseline: Any) -> List[str]:
    """Extract port ids along a RouteResult (path segments → from/to chain)."""
    if not baseline.path:
        return []
    ids = [baseline.path[0].from_port]
    for seg in baseline.path:
        if seg.to_port != ids[-1]:
            ids.append(seg.to_port)
    return ids


def _recommendation(assessment: Dict[str, Any], origin: str, destination: str) -> str:
    level = assessment["level"]
    alerts = assessment["alerts"]
    if level == "GREEN":
        return (
            f"Favorable weather along {origin} → {destination}. "
            "No weather-related delay expected — maintain planned schedule."
        )
    if level == "YELLOW":
        return (
            f"Minor weather on the {origin} → {destination} corridor. "
            "Monitor ports en route; small delays possible in exposed lanes."
        )
    if level == "ORANGE":
        worst = assessment["worst"]
        return (
            f"Disruptive weather ahead ({worst['label']}: {worst['summary']}). "
            "Consider adjusting departure windows, adding buffer time, or "
            "checking alternate routing around the affected area."
        )
    worst = assessment["worst"]
    return (
        f"Severe weather at {worst['label']} ({worst['summary']}). "
        f"{len(alerts)} hazardous point(s) on this route. "
        "Strongly consider delaying departure or rerouting until conditions clear."
    )
