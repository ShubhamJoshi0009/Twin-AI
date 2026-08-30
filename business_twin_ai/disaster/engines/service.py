"""ValidationService — the single entry point used by every report-creation API.

Flow (spec pipeline diagram):
    Incoming Report
        ↓ pipeline (location → metadata → image → duplicate → suspicious → confidence)
        ↓ store (or reject when invalid)
        ↓ cluster assignment
        ↓ map warning state update
        ↓ reporter trust update
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config
from business_twin_ai.disaster.engines.clustering import ClusteringService
from business_twin_ai.disaster.engines.reporter_trust import ReporterTrustService
from business_twin_ai.disaster.engines.warning_state import MapWarningStateUpdater
from business_twin_ai.disaster.models import DisasterReport, IncidentCluster
from business_twin_ai.disaster.utils.datetime_utils import parse_datetime
from business_twin_ai.disaster.validation.pipeline import PipelineResult, ValidationPipeline

logger = logging.getLogger("business_twin_ai.disaster.validation")


@dataclass
class SubmitResult:
    """What a report submission produced (used by routes + middleware)."""

    report_id: str
    validation: Dict[str, Any] = field(default_factory=dict)
    stored: bool = False
    rejected: bool = False
    status_code: int = 201
    payload: Dict[str, Any] = field(default_factory=dict)


class ValidationService:
    """Orchestrates validation, storage, clustering, trust and map warnings."""

    def __init__(
        self,
        db: AsyncSession,
        config: ValidationConfig = default_config,
        pipeline: Optional[ValidationPipeline] = None,
    ) -> None:
        self.db = db
        self.config = config
        self.pipeline = pipeline or ValidationPipeline(config=config)
        self.clustering = ClusteringService(db, config)
        self.warnings = MapWarningStateUpdater(config)
        self.trust = ReporterTrustService(db, config)

    # ── Public API ──────────────────────────────────────────────────────────

    async def submit_report(self, payload: Dict[str, Any]) -> SubmitResult:
        """Validate, store, cluster, update trust and map state (full pipeline)."""
        start = time.perf_counter()
        report_id = str(uuid.uuid4())
        payload = dict(payload)
        payload["report_id"] = report_id

        # Normalise the timestamp (ISO string → tz-aware datetime) so every
        # stage and the clustering engine can compare consistently.
        parsed_ts = parse_datetime(payload.get("timestamp"))
        if parsed_ts is None:
            parsed_ts = datetime.now(timezone.utc)
        payload["timestamp"] = parsed_ts

        # Precompute image hash once (used by duplicate + suspicious stages).
        raw_image = payload.get("image_base64")
        if raw_image:
            from business_twin_ai.disaster.utils.images import inspect_image
            from business_twin_ai.disaster.validation.image import decode_base64_image

            data = decode_base64_image(raw_image)
            if data is not None:
                inspection = inspect_image(data)
                payload["_image_hash"] = inspection.sha256
                if inspection.gps:
                    payload["_image_gps"] = inspection.gps

        # Reporter trust is injected so the confidence stage can use it.
        profile = await self.trust.get_or_create(payload["reporter_id"])
        payload["_reporter_trust"] = profile.reporter_trust_score

        result = await self.pipeline.run(payload, db=self.db)
        total_ms = (time.perf_counter() - start) * 1000.0

        # ── Reject invalid locations (never stored) ──
        if not result.location.valid_location:
            await self.trust.record_outcome(
                payload["reporter_id"],
                report_id,
                rejected=True,
                notes=[result.location.reason] if result.location.reason else None,
            )
            validation = self._build_validation(
                payload, result, report_id, None, None, total_ms
            )
            logger.info(
                "[validation] report %s REJECTED: %s", report_id, result.location.reason
            )
            return SubmitResult(
                report_id=report_id,
                validation=validation,
                stored=False,
                rejected=True,
                status_code=422,
                payload=payload,
            )

        # ── Cluster assignment (spec §5) ──
        cluster = await self._assign_cluster(payload, result)
        if cluster is not None:
            warning_level = self.warnings.update_warning_for(
                cluster.cluster_id,
                cluster.average_severity,
                cluster.report_count,
                cluster.disaster_type,
            )
        else:
            warning_level = "GREEN"

        # ── Store (spec §13) ──
        await self._store_report(payload, result, cluster, warning_level)
        logger.info(
            "[validation] report %s stored in %s (status=%s)",
            report_id,
            cluster.cluster_id if cluster else "-",
            result.validation_status,
        )

        # ── Reporter trust update ──
        await self.trust.record_outcome(
            payload["reporter_id"],
            report_id,
            accepted=True,
            duplicate=result.duplicate.duplicate,
            suspicious=result.suspicious.suspicious,
            notes=result.validation_notes,
        )
        updated_profile = await self.trust.get(payload["reporter_id"])
        trust_score = (
            updated_profile.reporter_trust_score
            if updated_profile
            else profile.reporter_trust_score
        )

        validation = self._build_validation(
            payload,
            result,
            report_id,
            cluster.cluster_id if cluster else None,
            warning_level,
            total_ms,
            trust_score=trust_score,
        )
        return SubmitResult(
            report_id=report_id,
            validation=validation,
            stored=True,
            rejected=False,
            status_code=201,
            payload=payload,
        )

    async def validate_only(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the pipeline without storing (POST /validate-report)."""
        start = time.perf_counter()
        report_id = str(uuid.uuid4())
        payload = dict(payload)
        payload["report_id"] = report_id
        parsed_ts = parse_datetime(payload.get("timestamp"))
        if parsed_ts is None:
            parsed_ts = datetime.now(timezone.utc)
        payload["timestamp"] = parsed_ts
        raw_image = payload.get("image_base64")
        if raw_image:
            from business_twin_ai.disaster.utils.images import inspect_image
            from business_twin_ai.disaster.validation.image import decode_base64_image

            data = decode_base64_image(raw_image)
            if data is not None:
                inspection = inspect_image(data)
                payload["_image_hash"] = inspection.sha256
                if inspection.gps:
                    payload["_image_gps"] = inspection.gps
        # Read-only trust lookup — validate-only must not persist anything.
        profile = await self.trust.get(payload["reporter_id"])
        payload["_reporter_trust"] = (
            profile.reporter_trust_score if profile else self.config.TRUST_START
        )

        result = await self.pipeline.run(payload, db=self.db)
        total_ms = (time.perf_counter() - start) * 1000.0
        cluster = await self._peek_cluster(payload, result)
        warning_level = "GREEN"
        if cluster is not None:
            warning_level = self.warnings.compute_warning_level(
                cluster.average_severity, cluster.report_count
            )
        trust_score = profile.reporter_trust_score if profile else self.config.TRUST_START
        return self._build_validation(
            payload,
            result,
            report_id,
            cluster.cluster_id if cluster else None,
            warning_level,
            total_ms,
            trust_score=trust_score,
        )

    # ── Internals ───────────────────────────────────────────────────────────

    async def _assign_cluster(
        self, payload: Dict[str, Any], result: PipelineResult
    ) -> Optional[IncidentCluster]:
        preferred = None
        if result.duplicate.duplicate and result.duplicate.duplicate_of:
            dup_report = await self.db.get(DisasterReport, uuid.UUID(result.duplicate.duplicate_of))
            if dup_report is not None:
                preferred = dup_report.cluster_id
        return await self.clustering.assign(
            latitude=payload["latitude"],
            longitude=payload["longitude"],
            disaster_type=payload["disaster_type"],
            severity=payload["severity"],
            timestamp=payload["timestamp"] or datetime.now(timezone.utc),
            preferred_cluster_id=preferred,
        )

    async def _peek_cluster(
        self, payload: Dict[str, Any], result: PipelineResult
    ) -> Optional[IncidentCluster]:
        """Find the cluster a report *would* join, without mutating anything."""
        if result.duplicate.duplicate and result.duplicate.duplicate_of:
            dup_report = await self.db.get(
                DisasterReport, uuid.UUID(result.duplicate.duplicate_of)
            )
            if dup_report is not None and dup_report.cluster_id:
                existing = await self.db.execute(
                    select(IncidentCluster).where(
                        IncidentCluster.cluster_id == dup_report.cluster_id
                    )
                )
                return existing.scalar_one_or_none()
        return None

    async def _store_report(
        self,
        payload: Dict[str, Any],
        result: PipelineResult,
        cluster: Optional[IncidentCluster],
        warning_level: str,
    ) -> DisasterReport:
        report = DisasterReport(
            id=uuid.UUID(payload["report_id"]),
            title=payload["title"],
            description=payload["description"],
            timestamp=payload["timestamp"] or datetime.now(timezone.utc),
            reporter_id=payload["reporter_id"],
            disaster_type=payload["disaster_type"],
            severity=payload["severity"],
            latitude=payload["latitude"],
            longitude=payload["longitude"],
            location_name=payload.get("location_name"),
            district=payload.get("district"),
            state=payload.get("state"),
            image_hash=payload.get("_image_hash"),
            image_metadata=result.image.image_metadata or None,
            location_score=result.location.location_score,
            metadata_score=result.metadata.metadata_score,
            image_score=result.image.image_score,
            confidence_score=result.confidence.confidence_score,
            duplicate_score=result.duplicate.duplicate_score,
            duplicate=result.duplicate.duplicate,
            duplicate_of=result.duplicate.duplicate_of,
            cluster_id=cluster.cluster_id if cluster else None,
            warning_level=warning_level,
            validation_status=result.validation_status,
            suspicious=result.suspicious.suspicious,
            validation_notes=result.validation_notes,
            reporter_trust_score=payload.get("_reporter_trust", self.config.TRUST_START),
        )
        self.db.add(report)
        await self.db.flush()
        return report

    def _build_validation(
        self,
        payload: Dict[str, Any],
        result: PipelineResult,
        report_id: str,
        cluster_id: Optional[str],
        warning_level: Optional[str],
        execution_time_ms: float,
        trust_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Shape the validation object exactly as the spec §9 shows."""
        trust = trust_score if trust_score is not None else payload.get(
            "_reporter_trust", self.config.TRUST_START
        )
        return {
            "report_id": report_id,
            "valid": result.valid,
            "confidence_score": result.confidence.confidence_score,
            "location_score": result.location.location_score,
            "metadata_score": result.metadata.metadata_score,
            "image_score": result.image.image_score,
            "duplicate": result.duplicate.duplicate,
            "duplicate_score": result.duplicate.duplicate_score,
            "suspicious": result.suspicious.suspicious,
            "suspicious_reasons": result.suspicious.reasons,
            "cluster_id": cluster_id,
            "warning_level": warning_level,
            "validation_status": result.validation_status,
            "reporter_trust_score": trust,
            "execution_time_ms": round(execution_time_ms, 2),
            "location": {
                "valid_location": result.location.valid_location,
                "precision_score": result.location.precision_score,
                "location_verified": result.location.location_verified,
                "reason": result.location.reason,
            },
            "metadata": {
                "metadata_score": result.metadata.metadata_score,
                "valid": result.metadata.valid,
                "warnings": result.metadata.warnings,
            },
            "image": {
                "image_valid": result.image.image_valid,
                "image_score": result.image.image_score,
                "image_metadata": result.image.image_metadata,
            },
            "duplicate_details": {
                "duplicate": result.duplicate.duplicate,
                "duplicate_score": result.duplicate.duplicate_score,
                "duplicate_of": result.duplicate.duplicate_of,
                "candidates_checked": result.duplicate.candidates_checked,
            },
            "suspicious_details": {
                "suspicious": result.suspicious.suspicious,
                "reasons": result.suspicious.reasons,
            },
            "confidence": {
                "confidence_score": result.confidence.confidence_score,
                "components": result.confidence.components,
            },
            "validation_notes": result.validation_notes,
        }
