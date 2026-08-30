# Real-Time Weather Monitoring for Supply Routes

Live weather conditions along the world shipping network, overlaid on the
Route Diversion map. Every port and sea lane shows current conditions and a
weather-risk level (GREEN / YELLOW / ORANGE / RED), and any selected voyage
gets an aggregated route assessment with an actionable recommendation.

## Architecture

```
Route Diversion map (frontend)
   ↓ auto-refresh every 60s
GET /supply-chain/routes/weather           ← all ports + lanes (one request)
GET /supply-chain/routes/weather/route     ← per-voyage weather + risk
   ↓
supply_chain/api/routes/weather.py         ← API schemas + aggregation
   ↓
services/weather/open_meteo.py             ← provider + TTL cache + fallback
   ↓
services/weather/risk.py                   ← hazard scoring + route aggregation
   ↓
Open-Meteo (free, no API key)  ── unreachable? ──▶  simulated conditions
```

Provider choice mirrors the news stack: **Open-Meteo** is free and needs no
API key (like GDELT), and every fetch falls back to deterministic simulated
conditions when the provider is unreachable — so the map always renders and
never goes empty. `mode: "live" | "simulated"` in every response tells the UI
which source it's looking at.

### Module layout

| Path | Responsibility |
|------|----------------|
| `services/weather/open_meteo.py` | Batched Open-Meteo client, in-process TTL cache, deterministic simulated fallback |
| `services/weather/risk.py` | WMO-code mapping, hazard scoring (0-100), route aggregation, alerts |
| `supply_chain/api/routes/weather.py` | `/routes/weather` + `/routes/weather/route` endpoints |
| `frontend/src/components/route-diversion/world-map.tsx` | Weather overlay (port rings, lane tints, badge) |
| `frontend/src/app/(dashboard)/route-diversion/page.tsx` | Live Weather Monitor panel |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/supply-chain/routes/weather` | Current weather at all 28 ports + per-lane risk + alerts + summary |
| `GET` | `/api/v1/supply-chain/routes/weather/route?origin=&destination=` | Weather + aggregated risk along the baseline route between two ports |

Both return `mode`, `generated_at`, per-point `conditions`
(`temperature_c`, `wind_speed_kmh`, `wind_gusts_kmh`, `precipitation_mm`,
`weather_code`, `weather_label`, `weather_icon`, `relative_humidity`,
`observed_at`, `source`), a 0-100 `risk_score` and a `risk_level`
(GREEN/YELLOW/ORANGE/RED), plus `summary` / `alerts`.

### Example

```bash
curl "http://localhost:8000/api/v1/supply-chain/routes/weather/route?origin=shanghai&destination=rotterdam"
```

```json
{
  "mode": "simulated",
  "origin": "shanghai",
  "destination": "rotterdam",
  "overall_risk_score": 33.6,
  "overall_level": "YELLOW",
  "points": [
    {
      "label": "Shanghai",
      "lat": 31.23,
      "lng": 121.47,
      "risk_score": 18.0,
      "risk_level": "GREEN",
      "summary": "Partly cloudy, +23°C, 22 km/h wind",
      "conditions": { "temperature_c": 23.1, "wind_speed_kmh": 22.0, "weather_icon": "⛅", "source": "simulated" }
    }
  ],
  "alerts": [],
  "recommendation": "Favorable weather along shanghai → rotterdam. No weather-related delay expected — maintain planned schedule."
}
```

## Risk model (`services/weather/risk.py`)

Each location's 0-100 score is the sum of explainable hazards:

| Hazard | Contribution | Thresholds |
|--------|--------------|------------|
| Wind (sustained/gusts) | 0-40 | ≥25 km/h minor → ≥40 moderate → ≥60 strong → ≥85 gale |
| Precipitation | 0-25 | ≥1 mm → ≥5 → ≥15 → ≥30 mm |
| Severe WMO code | 0-26 | thunderstorms (95-99), heavy rain (65/67/82), heavy snow (75/86) |
| Temperature extremes | 0-9 | ≥38°C heat, ≤-5°C cold (cold-chain cargo) |

Score → level: `<25 GREEN`, `25-49 YELLOW`, `50-74 ORANGE`, `≥75 RED`.

Route aggregation = `0.6 × average + 0.4 × worst point` (a single violent
storm on a long route still matters), with ORANGE/RED points surfaced as
alerts and a plain-language recommendation per level.

## Real-time behaviour

- The frontend refreshes weather every **60 seconds** (`useRouteWeather` /
  `useRouteWeatherDetail` with `refetchInterval`), so the map and panel track
  changing conditions without user action.
- The backend caches per-coordinate conditions for
  `WEATHER_CACHE_TTL_SECONDS` (default 5 min) and fetches all stale ports in
  **one** batched Open-Meteo request — "real-time" is a fresh TTL read, not a
  round-trip per port.
- Simulated conditions drift every 15 minutes, so an offline demo still looks
  alive.

## Configuration (`config.py`)

| Var | Default | Meaning |
|-----|---------|---------|
| `WEATHER_API_URL` | `https://api.open-meteo.com/v1/forecast` | Free endpoint (no key) |
| `WEATHER_API_KEY` | `""` | Optional — switches to the commercial `customer-api.open-meteo.com` |
| `WEATHER_CACHE_TTL_SECONDS` | `300` | In-process per-coordinate cache TTL |
| `WEATHER_FORCE_SIMULATED` | `false` | Bypass the network (offline demos / deterministic tests) |

## Map display (frontend)

- **Ports** get a colored ring by weather level (RED rings pulse); origin and
  destination also show a weather chip (`⛅ 23°C · GREEN`).
- **Sea lanes / rail corridors** are tinted by their worst endpoint port.
- A **Weather badge** (top-left) shows the global worst level + alert count.
- The **Live Weather Monitor** panel shows the route-level assessment,
  hazard alerts, and per-port weather chips, with a refresh button and a
  "Live · Open-Meteo / Simulated · offline" source badge.

## Tests

`tests/test_route_weather.py` — runs fully offline with
`WEATHER_FORCE_SIMULATED=true`:

- WMO label mapping (incl. unknown codes), risk-level thresholds, monotonic
  hazard scoring, route aggregation, `worst_level`.
- Simulated fallback determinism + plausibility, batched-fetch dedupe.
- API: overlay shape (28 ports, 40 lanes), per-route detail, 422 validation
  (unknown/same/missing ports), and a route-simulator regression check.

```bash
pytest tests/test_route_weather.py -v
```

## Extension points

| Point | Where | Notes |
|-------|-------|-------|
| Keyed provider | `open_meteo.py` + `WEATHER_API_KEY` | Switches to Open-Meteo commercial endpoint automatically |
| Forecast horizon | `open_meteo.py` | `hourly`/`daily` variables + `forecast_days` — extend for route ETAs |
| Risk weights | `risk.py` | Hazard ceilings are constants; adjust per fleet/industry |
| New overlays | `world-map.tsx` | Weather prop is optional — add wind/precip legends easily |
| Chokepoint weather | `weather.py` | Sample mid-lane coordinates instead of endpoint ports |
| Alerting | panel + `weather.py` | Add thresholds per cargo type (cold-chain, deck cargo) |
