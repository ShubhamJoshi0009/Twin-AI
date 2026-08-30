# Disaster / Emergency Report Validation Layer

A modular validation pipeline for disaster/emergency reports. Every incoming
report passes through an independent stage pipeline before it is stored, and
the disaster-map warning state is updated automatically.

## Architecture

```
Incoming Report
   ↓ ValidationMiddleware (ASGI)          spec §11 — all creation APIs
   ↓ ValidationService.submit_report()    orchestrator
   ↓ ValidationPipeline
       ├─ Location Validation             spec §1
       ├─ Metadata Validation             spec §2
       ├─ Image Validation                spec §3
       ├─ Duplicate Detection             spec §4
       ├─ Suspicious Detection            spec §6
       └─ Confidence Score                spec §7
   ↓ ClusteringService                    spec §5 — assign/create incident cluster
   ↓ Store Report                         spec §13 — extended model + indexes
   ↓ MapWarningStateUpdater               spec §10 — GREEN/YELLOW/ORANGE/RED
   ↓ ReporterTrustService                 spec §8  — update reporter trust
```

### Module layout (`business_twin_ai/disaster/`)

| Path | Responsibility |
|------|----------------|
| `config.py` | All tunable thresholds & weights (`ValidationConfig`) |
| `models/database.py` | `DisasterReport`, `IncidentCluster`, `ReporterProfile` ORM models |
| `schemas/schemas.py` | Pydantic request/response schemas |
| `validation/location.py` | Location stage |
| `validation/metadata.py` | Metadata stage |
| `validation/image.py` | Image stage (dependency-free inspector) |
| `validation/duplicates.py` | Duplicate detection stage |
| `validation/suspicious.py` | Suspicious-report heuristics |
| `validation/confidence.py` | Confidence weighting |
| `validation/pipeline.py` | Runs stages in order, per-stage timing + logging |
| `engines/clustering.py` | Incident cluster create/join |
| `engines/warning_state.py` | Map warning level + TTL cache |
| `engines/reporter_trust.py` | Reporter trust score + history |
| `engines/service.py` | `ValidationService` (validate → store → cluster → warn → trust) |
| `middleware.py` | ASGI `ValidationMiddleware` |
| `api/routes/` | New API endpoints |
| `utils/` | geo, text, datetime, pure-Python image inspection helpers |

Each stage is fully independent: it receives a `StageContext` and returns a
small result object; no stage calls another. The pipeline orchestrates them and
records per-stage execution times.

## API

All endpoints are namespaced under `/api/v1/disaster` so existing endpoints
(such as the PDF report generator under `/api/v1/reports`) are untouched.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/disaster/reports` | Create a report — full pipeline + store (middleware enforces validation) |
| `POST` | `/api/v1/disaster/validate-report` | Run the pipeline without storing |
| `GET` | `/api/v1/disaster/report/{id}/validation` | Stored validation summary |
| `GET` | `/api/v1/disaster/reports/duplicates` | Reports flagged as duplicates |
| `GET` | `/api/v1/disaster/reports/suspicious` | Reports flagged as suspicious |
| `GET` | `/api/v1/disaster/clusters` | All incident clusters |
| `GET` | `/api/v1/disaster/clusters/{cluster_id}` | Cluster detail + member reports |
| `GET` | `/api/v1/disaster/map/warnings` | Per-cluster warning state + level summary |

### Example request

```bash
curl -X POST http://localhost:8000/api/v1/disaster/reports \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Flash flood hits riverside colony",
    "description": "Riverside colony submerged after heavy rain; residents need evacuation.",
    "timestamp": "2026-08-08T10:30:00Z",
    "reporter_id": "riverside-watch",
    "disaster_type": "flood",
    "severity": 7.0,
    "latitude": 28.6129,
    "longitude": 77.2295,
    "location_name": "Riverside Colony",
    "district": "Central",
    "state": "Delhi"
  }'
```

### Example response

```json
{
  "report_id": "3f9b1a2c-...",
  "validation": {
    "valid": true,
    "confidence_score": 86.4,
    "location_score": 90.0,
    "metadata_score": 92.0,
    "image_score": 50.0,
    "duplicate": false,
    "duplicate_score": 12.4,
    "suspicious": false,
    "suspicious_reasons": [],
    "cluster_id": "cluster_1",
    "warning_level": "YELLOW",
    "validation_status": "valid",
    "reporter_trust_score": 52.0,
    "execution_time_ms": 8.2,
    "location": { "valid_location": true, "precision_score": 80.0, "location_verified": true, "reason": null },
    "metadata": { "metadata_score": 92.0, "valid": true, "warnings": [] },
    "image": { "image_valid": true, "image_score": 50.0, "image_metadata": { "present": false } },
    "duplicate_details": { "duplicate": false, "duplicate_score": 12.4, "duplicate_of": null, "candidates_checked": 3 },
    "suspicious_details": { "suspicious": false, "reasons": [] },
    "confidence": { "confidence_score": 86.4, "components": { "location": 90.0, "metadata": 92.0, "image": 50.0, "duplicate": 87.6, "trust": 52.0 } },
    "validation_notes": []
  }
}
```

## Validation rules

### Location (`validation/location.py`)
- `latitude`/`longitude` must exist, fall in `[-90, 90]` / `[-180, 180]`, and not be `(0, 0)`.
- `precision_score` derives from the number of decimal places (GPS precision).
- `location_verified` reflects a present `location_name` (reverse geocoding is an
  optional extension point, disabled by default via `REVERSE_GEOCODE_ENABLED`).
- Invalid locations **reject** the report (`422`, never stored).

### Metadata (`validation/metadata.py`)
- Required fields: `title`, `description`, `timestamp`, `reporter_id`,
  `disaster_type`, `severity`.
- Length checks, spam-word detection, repeated characters, empty/short text,
  invalid and future timestamps. Produces `metadata_score` (0-100).

### Image (`validation/image.py`)
- Pure-Python inspector: format sniffing (JPEG/PNG/GIF/WebP/BMP), dimensions,
  SHA-256 hash, JPEG EXIF GPS + timestamp, basic corruption detection.
- A **missing image never rejects the report** — it halves the image component
  (neutral `50.0` score), reducing confidence only.

### Duplicates (`validation/duplicates.py`)
- Weighted similarity over GPS proximity, time proximity, image-hash equality,
  text similarity, disaster type and severity. Scores 0-100.
- `duplicate_score > 85` → `duplicate: true`, `duplicate_of` set to the best
  candidate, and the report joins that candidate's cluster.
- Queries are pre-filtered by time window + bounding box and use the
  `(latitude, longitude)` index.

### Suspicious (`validation/suspicious.py`)
Heuristics (any hit → `suspicious: true` with `reasons[]`):
- GPS far from image GPS (when both present)
- Reporter flooding (> N reports/hour)
- Copied description (text similarity ≥ 0.90 to a recent report)
- Same image reused
- Future timestamps
- Impossible movement speed (> 900 km/h over a meaningful time gap)
- Rounded/grid-aligned coordinates
- Very low metadata or image score

### Confidence (`validation/confidence.py`)
Weighted blend (spec §7): location 30%, metadata 20%, image 20%, duplicate 15%
(inverted — high duplicate score lowers confidence), reporter trust 15%.

### Reporter trust (`engines/reporter_trust.py`)
Start at 50, range 0-100, updated after **every** report:
accepted +2, rejected −10, duplicate −3, suspicious −5, false −15. History kept
in `verification_history` (last 50 entries).

### Map warning state (`engines/warning_state.py`)
Per cluster, from `average_severity` + `report_count`:

| Level | Rule (defaults in `ValidationConfig`) |
|-------|----------------------------------------|
| RED | `severity > 8` AND `reports > 20` |
| ORANGE | `severity ≥ 7` AND `reports ≥ 10` |
| YELLOW | `severity ≥ 4` AND `reports ≥ 3` |
| GREEN | otherwise (e.g. `severity < 3` AND `reports < 3`) |

Cluster lookups are cached with a 30-second TTL (`WARNING_CACHE_TTL_SECONDS`)
and invalidated on writes.

## Middleware (spec §11)

`ValidationMiddleware` intercepts `POST /api/v1/disaster/reports` and runs
`ValidationService.submit_report()` directly — controllers contain **no**
validation logic. The route handler exists as the documented API surface and
runs the same service (used when the middleware is not installed). All other
paths pass through untouched, so existing endpoints are unaffected.

## Database (spec §13)

Tables (created automatically by `init_db()`):
- `disaster_reports` — full report + all validation fields, with indexes on
  `cluster_id`, `(latitude, longitude)`, `timestamp`, `reporter_id`, `duplicate`.
- `incident_clusters` — center, report count, average severity, warning level.
- `reporter_profiles` — trust score, outcome counters, verification history.

## Performance (spec §16)

- Pipeline is pure-Python + bounded indexed queries — a normal report validates
  in single-digit milliseconds (well under the 200 ms budget).
- Duplicate detection pre-filters by bounding box + time window.
- Cluster/warning state is TTL-cached.
- Image analysis is CPU-cheap; `IMAGE_ANALYSIS_ASYNC` is the documented extension
  point for moving inspection to a worker pool / external service.

## Extension points

| Point | Where | Notes |
|-------|-------|-------|
| Reverse geocoding | `location.py` (guarded by `REVERSE_GEOCODE_ENABLED`) | Plug a geocoder adapter |
| Image analysis backend | `utils/images.py` + `IMAGE_ANALYSIS_ASYNC` | Swap in Pillow / async workers |
| Thresholds & weights | `ValidationConfig` | All tunables in one place |
| New stages | implement `ValidationStage` + add to `ValidationPipeline` | Independent by design |
| Spatial scaling | `clustering.py` / `duplicates.py` | Swap bounding-box pre-filter for PostGIS/R-tree |
| Warning rules | `warning_state.py` + config | Pure function, easy to extend |

## Tests

- `tests/test_disaster_validation_units.py` — unit tests for every stage and
  heuristic (valid/invalid GPS, missing metadata, future timestamps, image
  success/failure, duplicate thresholds, suspicious heuristics, confidence).
- `tests/test_disaster_validation_pipeline.py` — end-to-end pipeline, cluster
  creation/aggregation, warning transitions, reporter trust updates, the 200 ms
  budget, and the demo cases (genuine, duplicate, fake w/ reused image, invalid
  location, RED cluster).
- `tests/test_disaster_validation_api.py` — API integration incl. middleware
  path, validation retrieval, clusters/duplicates/suspicious/map endpoints, and
  confirmation that existing endpoints (`/health`) still work.

```bash
pytest tests/test_disaster_validation_units.py tests/test_disaster_validation_pipeline.py tests/test_disaster_validation_api.py -v
```
