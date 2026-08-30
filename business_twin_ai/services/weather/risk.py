"""Weather risk scoring for supply routes.

Turns raw weather conditions into a 0-100 risk score and a warning level
(GREEN / YELLOW / ORANGE / RED) per location, then aggregates across a route
(ports + sea lanes) into an overall route risk with actionable alerts.

The scoring is deliberately explainable: each hazard (wind, precipitation,
thunderstorms, temperature extremes) contributes an additive score with a
known ceiling, so a RED route is easy to trace back to "65 km/h gusts at
Aden".
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

# Warning levels shared with the disaster map (spec §10 vocabulary).
GREEN = "GREEN"
YELLOW = "YELLOW"
ORANGE = "ORANGE"
RED = "RED"

LEVEL_ORDER = (GREEN, YELLOW, ORANGE, RED)

# Thresholds for the aggregated score → level mapping.
LEVEL_THRESHOLDS: Tuple[Tuple[str, float], ...] = (
    (RED, 75.0),
    (ORANGE, 50.0),
    (YELLOW, 25.0),
    (GREEN, 0.0),
)

# WMO weather codes that are inherently disruptive to shipping.
_SEVERE_CODES: Dict[int, float] = {
    95: 18.0, 96: 22.0, 99: 26.0,   # thunderstorms
    65: 14.0, 67: 16.0, 82: 18.0,   # heavy rain / violent showers
    75: 12.0, 86: 12.0,             # heavy snow
}


def risk_level(score: float) -> str:
    """Map a 0-100 risk score to GREEN/YELLOW/ORANGE/RED."""
    for level, threshold in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return GREEN


def hazard_breakdown(conditions: Dict[str, Any]) -> Dict[str, float]:
    """Named per-hazard scores so alerts can say *why* a location is risky."""
    wind = float(conditions.get("wind_speed_kmh") or 0.0)
    gusts = float(conditions.get("wind_gusts_kmh") or wind)
    precip = float(conditions.get("precipitation_mm") or 0.0)
    temp = float(conditions.get("temperature_c") or 0.0)
    code = int(conditions.get("weather_code") or 0)

    # Wind (max of sustained / gusts): 0-40 pts. Shipping starts feeling it
    # around 40 km/h; >85 km/h is severe (gale force).
    wind_eff = max(wind, gusts)
    if wind_eff >= 85:
        wind_score = 40.0
    elif wind_eff >= 60:
        wind_score = 28.0
    elif wind_eff >= 40:
        wind_score = 16.0
    elif wind_eff >= 25:
        wind_score = 7.0
    else:
        wind_score = 0.0

    # Precipitation (mm): 0-25 pts.
    if precip >= 30:
        precip_score = 25.0
    elif precip >= 15:
        precip_score = 18.0
    elif precip >= 5:
        precip_score = 10.0
    elif precip >= 1:
        precip_score = 4.0
    else:
        precip_score = 0.0

    # Severe WMO code (thunderstorm / heavy rain / heavy snow): 0-26 pts.
    code_score = _SEVERE_CODES.get(code, 0.0)

    # Temperature extremes (cold-chain cargo, deck ops): 0-9 pts.
    if temp >= 42:
        temp_score = 9.0
    elif temp >= 38:
        temp_score = 5.0
    elif temp <= -15:
        temp_score = 8.0
    elif temp <= -5:
        temp_score = 4.0
    else:
        temp_score = 0.0

    return {
        "wind": round(wind_score, 1),
        "precipitation": round(precip_score, 1),
        "weather_code": round(code_score, 1),
        "temperature": round(temp_score, 1),
    }


def conditions_risk(conditions: Dict[str, Any]) -> Dict[str, Any]:
    """Score one weather sample: ``{risk_score, level, hazards, summary}``."""
    hazards = hazard_breakdown(conditions)
    score = round(sum(hazards.values()), 1)
    score = max(0.0, min(100.0, score))
    level = risk_level(score)
    summary = _summary(conditions, level, hazards)
    return {"risk_score": score, "level": level, "hazards": hazards, "summary": summary}


def _summary(conditions: Dict[str, Any], level: str, hazards: Dict[str, float]) -> str:
    label = conditions.get("weather_label") or "Unknown"
    temp = conditions.get("temperature_c")
    wind = conditions.get("wind_speed_kmh")
    bits = [f"{label}"]
    if temp is not None:
        bits.append(f"{temp:+.0f}°C")
    if wind is not None:
        bits.append(f"{wind:.0f} km/h wind")
    if hazards["wind"] >= 16:
        bits.append("strong gusts")
    if hazards["precipitation"] >= 10:
        bits.append("heavy precipitation")
    if hazards["weather_code"] >= 12:
        bits.append("storm activity")
    return ", ".join(bits)


def route_weather_risk(
    points: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate per-location scores into a route-level assessment.

    ``points``: list of ``{lat, lng, label, conditions}`` dicts (ports /
    waypoints along the route). Returns overall score + level, the worst
    location, and alerts for any ORANGE/RED point.
    """
    scored: List[Dict[str, Any]] = []
    for pt in points:
        conditions = pt.get("conditions") or {}
        result = conditions_risk(conditions)
        scored.append({
            "label": pt.get("label") or f"{pt.get('lat')},{pt.get('lng')}",
            "lat": pt.get("lat"),
            "lng": pt.get("lng"),
            "risk_score": result["risk_score"],
            "level": result["level"],
            "summary": result["summary"],
            "conditions": conditions,
        })

    if not scored:
        return {
            "risk_score": 0.0,
            "level": GREEN,
            "worst": None,
            "alerts": [],
            "points": [],
        }

    # Overall = average, nudged up when any single point is severe (a single
    # violent storm on a long route still matters).
    avg = sum(s["risk_score"] for s in scored) / len(scored)
    worst_score = max(s["risk_score"] for s in scored)
    overall = round(avg * 0.6 + worst_score * 0.4, 1)
    worst = max(scored, key=lambda s: s["risk_score"])

    alerts: List[Dict[str, Any]] = []
    for s in scored:
        if s["level"] in (ORANGE, RED):
            alerts.append({
                "location": s["label"],
                "lat": s["lat"],
                "lng": s["lng"],
                "level": s["level"],
                "risk_score": s["risk_score"],
                "summary": s["summary"],
            })

    return {
        "risk_score": overall,
        "level": risk_level(overall),
        "worst": worst,
        "alerts": alerts,
        "points": scored,
    }


def worst_level(*levels: Optional[str]) -> str:
    """Highest of several levels (RED > ORANGE > YELLOW > GREEN)."""
    present = [lvl for lvl in levels if lvl]
    if not present:
        return GREEN
    # Iterate worst → best so the first present level is the highest.
    for level in reversed(LEVEL_ORDER):
        if level in present:
            return level
    return GREEN
