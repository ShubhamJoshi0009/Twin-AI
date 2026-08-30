"""Real-time weather client backed by the free Open-Meteo API.

Open-Meteo (https://open-meteo.com) is free and needs no API key — exactly the
pattern the app already uses for GDELT news. We fetch current conditions
(temperature, wind, precipitation, WMO weather code, humidity) at arbitrary
lat/lng coordinates along shipping routes.

Because dev / CI sandboxes may be offline, every fetch falls back to
deterministic *simulated* conditions derived from the coordinate + a time
bucket, so the route-weather map always renders. With network access at
runtime it returns live Open-Meteo data.

Key design points:
* Coordinates are fetched in **batches** (Open-Meteo accepts comma-separated
  lat/lng lists) so the whole shipping network (28 ports) is one request.
* Results are cached in-process for ``WEATHER_CACHE_TTL_SECONDS`` per
  coordinate — "real-time" means a fresh TTL read, not a new HTTP round-trip
  per map render.
* ``WEATHER_FORCE_SIMULATED`` bypasses the network entirely (deterministic
  tests, fully-offline demos).
"""

from __future__ import annotations

import hashlib
import logging
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import httpx

from business_twin_ai.config import settings

logger = logging.getLogger(__name__)

WEATHER_TIMEOUT_SECONDS = 3.0
WEATHER_CONNECT_TIMEOUT_SECONDS = 1.5

# In-process TTL cache: (rounded lat, rounded lng) -> (expires_at, conditions)
_cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}

# Round to ~1.1 km so nearby ports / repeated lookups share a cache entry.
_COORD_PRECISION = 2

# WMO weather codes -> human label + emoji (subset used for route displays).
WMO_LABELS: Dict[int, Tuple[str, str]] = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Dense drizzle", "🌧️"),
    56: ("Freezing drizzle", "🌧️"),
    57: ("Dense freezing drizzle", "🌧️"),
    61: ("Light rain", "🌦️"),
    63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    66: ("Freezing rain", "🌧️"),
    67: ("Heavy freezing rain", "⛈️"),
    71: ("Light snow", "🌨️"),
    73: ("Snow", "🌨️"),
    75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Light showers", "🌦️"),
    81: ("Showers", "🌧️"),
    82: ("Violent showers", "⛈️"),
    85: ("Snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm, hail", "⛈️"),
    99: ("Severe thunderstorm, hail", "⛈️"),
}


def weather_label(code: int) -> Tuple[str, str]:
    """Human label + emoji for a WMO weather code (safe for any int)."""
    if code in WMO_LABELS:
        return WMO_LABELS[code]
    # Default: map by first digit family so unknown codes still read sensibly.
    if code >= 95:
        return ("Thunderstorm", "⛈️")
    if 71 <= code <= 86:
        return ("Snow", "🌨️")
    if 51 <= code <= 67:
        return ("Rain", "🌧️")
    if code in (45, 48):
        return ("Fog", "🌫️")
    return ("Cloudy", "☁️")


def _coord_key(lat: float, lng: float) -> Tuple[float, float]:
    return (round(lat, _COORD_PRECISION), round(lng, _COORD_PRECISION))


# ── Simulated fallback ────────────────────────────────────────────────────────
# Deterministic "plausible" weather from (lat, lng, time bucket). The same
# coordinate + bucket always yields the same conditions, so the map is stable
# between refreshes but changes over time — convincingly live, fully offline.

_SIM_BUCKET_SECONDS = 15 * 60  # conditions drift every 15 minutes


def _simulated_conditions(lat: float, lng: float) -> Dict[str, Any]:
    """Deterministic pseudo-weather for offline / unreachable-provider cases."""
    bucket = int(_time.time() // _SIM_BUCKET_SECONDS)
    seed = f"{lat:.4f}:{lng:.4f}:{bucket}".encode()
    digest = hashlib.sha256(seed).digest()

    def pick(span: int) -> int:
        return int.from_bytes(digest[span : span + 2], "big")

    # Warm near equator, cold at poles; wobble by bucket so it evolves.
    seasonal = pick(0) / 65535 * 10 - 5
    base_c = 28.0 - abs(lat) * 0.55 + seasonal

    code_roll = pick(2) % 100
    if code_roll < 45:
        code = 0 if code_roll < 20 else (2 if code_roll < 35 else 3)
    elif code_roll < 60:
        code = 61 if code_roll < 55 else 63
    elif code_roll < 70:
        code = 45
    elif code_roll < 80:
        code = 80 if code_roll < 75 else 95
    elif code_roll < 90:
        code = 71 if code_roll < 85 else 73
    else:
        code = 65

    temp_c = round(base_c + (pick(4) / 65535 * 6 - 3), 1)
    wind_kmh = round(pick(6) / 65535 * 55 + 5, 1)
    gust_kmh = round(wind_kmh * (1.3 + pick(8) / 65535 * 0.5), 1)
    precip_mm = round(pick(10) / 65535 * (8.0 if code >= 51 else 1.2), 1)
    humidity = round(35 + pick(12) / 65535 * 55, 0)

    label, icon = weather_label(code)
    # Deterministic observed time derived from the bucket (stable across calls).
    observed = datetime.fromtimestamp(
        bucket * _SIM_BUCKET_SECONDS, tz=timezone.utc
    ) - timedelta(minutes=pick(14) % 10)
    return {
        "temperature_c": temp_c,
        "apparent_temperature_c": round(temp_c - wind_kmh * 0.06, 1),
        "wind_speed_kmh": wind_kmh,
        "wind_gusts_kmh": gust_kmh,
        "precipitation_mm": precip_mm,
        "relative_humidity": humidity,
        "weather_code": code,
        "weather_label": label,
        "weather_icon": icon,
        "is_day": True,
        "observed_at": observed.isoformat(),
        "source": "simulated",
    }


# ── Live Open-Meteo ───────────────────────────────────────────────────────────

def _value_at(current: Dict[str, Any], key: str, index: int) -> Any:
    """Per-location value for a key.

    Open-Meteo returns *scalars* for a single-location request but *arrays*
    (one entry per location, in request order) for multi-location requests.
    ``index`` is the position of this point in the original request.
    """
    val = current.get(key)
    if isinstance(val, list):
        if index < len(val):
            return val[index]
        return val[-1] if val else None
    return val


def _parse_current(
    data: Dict[str, Any], lat: float, lng: float, index: int = 0
) -> Dict[str, Any]:
    """Normalize one location's Open-Meteo payload into app conditions.

    Accepts a single-location payload (``current`` with scalar values) or a
    multi-location payload (``current`` values as arrays, indexed by
    ``index``). The array format is returned by Open-Meteo when a request
    mixes `current` and `daily` blocks; the primary batch path uses the
    list-of-payloads format handled in ``_fetch_live_batch``.
    """
    current = (data or {}).get("current") or {}
    if not current or _value_at(current, "temperature_2m", index) is None:
        raise ValueError("Open-Meteo response missing current weather")

    code = int(_value_at(current, "weather_code", index) or 0)
    label, icon = weather_label(code)
    observed = _value_at(current, "time", index)
    return {
        "temperature_c": round(float(_value_at(current, "temperature_2m", index) or 0.0), 1),
        "apparent_temperature_c": round(
            float(_value_at(current, "apparent_temperature", index) or 0.0), 1
        ),
        "wind_speed_kmh": round(float(_value_at(current, "wind_speed_10m", index) or 0.0), 1),
        "wind_gusts_kmh": round(float(_value_at(current, "wind_gusts_10m", index) or 0.0), 1),
        "precipitation_mm": round(float(_value_at(current, "precipitation", index) or 0.0), 2),
        "relative_humidity": round(
            float(_value_at(current, "relative_humidity_2m", index) or 0.0), 0
        ),
        "weather_code": code,
        "weather_label": label,
        "weather_icon": icon,
        "is_day": bool(int(_value_at(current, "is_day", index) or 1)),
        "observed_at": observed or datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }


async def fetch_weather_batch(
    points: List[Tuple[float, float]],
) -> Dict[Tuple[float, float], Dict[str, Any]]:
    """Fetch current weather for many coordinates (one batched HTTP request).

    Returns ``{(lat, lng): conditions}`` keyed by the *rounded* coordinate.
    Falls back per-point to simulated conditions when the provider is
    unreachable, so callers always receive every requested point.
    """
    out: Dict[Tuple[float, float], Dict[str, Any]] = {}
    now = _time.monotonic()
    ttl = max(1, int(settings.WEATHER_CACHE_TTL_SECONDS))

    stale: List[Tuple[float, float]] = []
    for lat, lng in points:
        key = _coord_key(lat, lng)
        hit = _cache.get(key)
        if hit and hit[0] > now:
            out[key] = dict(hit[1])
        else:
            stale.append(key)

    if not stale:
        return out

    results: Dict[Tuple[float, float], Dict[str, Any]] = {}
    if not settings.WEATHER_FORCE_SIMULATED:
        results = await _fetch_live_batch(stale)

    for lat, lng in stale:
        key = _coord_key(lat, lng)
        conditions = results.get(key) or _simulated_conditions(lat, lng)
        _cache[key] = (now + ttl, conditions)
        out[key] = dict(conditions)
    return out


async def _fetch_live_batch(
    points: List[Tuple[float, float]],
) -> Dict[Tuple[float, float], Dict[str, Any]]:
    """One Open-Meteo request for all stale points; {} on any failure."""
    if not points:
        return {}
    try:
        lats = ",".join(f"{lat:.4f}" for lat, _ in points)
        lngs = ",".join(f"{lng:.4f}" for _, lng in points)
        params: Dict[str, Any] = {
            "latitude": lats,
            "longitude": lngs,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "precipitation,weather_code,wind_speed_10m,wind_gusts_10m,is_day"
            ),
            "timezone": "UTC",
            "forecast_days": 1,
        }
        url = settings.WEATHER_API_URL
        if settings.WEATHER_API_KEY:
            url = url.replace("api.open-meteo.com", "customer-api.open-meteo.com")
            params["apikey"] = settings.WEATHER_API_KEY
        timeout = httpx.Timeout(
            WEATHER_TIMEOUT_SECONDS,
            connect=WEATHER_CONNECT_TIMEOUT_SECONDS,
            pool=WEATHER_CONNECT_TIMEOUT_SECONDS,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        out: Dict[Tuple[float, float], Dict[str, Any]] = {}
        if isinstance(data, list):
            # Primary multi-location format: one payload object per location,
            # in request order. Each element carries its own ``current`` block.
            for index, (lat, lng) in enumerate(points):
                payload = data[index] if index < len(data) else {}
                key = _coord_key(lat, lng)
                out[key] = _parse_current(payload, lat, lng)
        else:
            # Single-location payload, or array-valued multi-location payload.
            for index, (lat, lng) in enumerate(points):
                key = _coord_key(lat, lng)
                out[key] = _parse_current(data, lat, lng, index=index)
        return out
    except Exception as exc:  # noqa: BLE001 — network/timeout/parse — fall back per point
        logger.info(
            "Open-Meteo unavailable (%s) — using simulated weather for %d point(s)",
            exc, len(points),
        )
        return {}


async def fetch_weather(lat: float, lng: float) -> Dict[str, Any]:
    """Current weather at one coordinate (cached, fallback-safe)."""
    batch = await fetch_weather_batch([(lat, lng)])
    return batch[_coord_key(lat, lng)]
