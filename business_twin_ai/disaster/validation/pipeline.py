"""Validation pipeline: runs each independent stage in order (spec pipeline diagram).

Incoming Report
    ↓ Location Validation
    ↓ Metadata Validation
    ↓ Image Validation
    ↓ Duplicate Detection
    ↓ Suspicious Detection
    ↓ Confidence Score
    ↓ Store Report
    ↓ Update Map Warning State
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.config import config as default_config
from business_twin_ai.disaster.validation.base import StageContext, log_stage, logger
from business_twin_ai.disaster.validation.confidence import ConfidenceResult, ConfidenceStage
from business_twin_ai.disaster.validation.duplicates import DuplicateDetectionStage, DuplicateResult
from business_twin_ai.disaster.validation.image import ImageResult, ImageValidationStage
from business_twin_ai.disaster.validation.location import LocationResult, LocationValidationStage
from business_twin_ai.disaster.validation.metadata import MetadataResult, MetadataValidationStage
from business_twin_ai.disaster.validation.suspicious import (
    SuspiciousDetectionStage,
    SuspiciousResult,
)

__all__ = ["PipelineResult", "ValidationPipeline", "logger"]


@dataclass
class PipelineResult:
    """Aggregated output of the validation pipeline."""

    location: LocationResult
    metadata: MetadataResult
    image: ImageResult
    duplicate: DuplicateResult
    suspicious: SuspiciousResult
    confidence: ConfidenceResult
    stage_times: Dict[str, float] = field(default_factory=dict)
    validation_notes: List[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        """A report is valid when location + metadata pass (image is soft)."""
        return self.location.valid_location and self.metadata.valid

    @property
    def validation_status(self) -> str:
        if not self.location.valid_location or not self.metadata.valid:
            return "rejected"
        if self.duplicate.duplicate:
            return "duplicate"
        if self.suspicious.suspicious:
            return "flagged"
        return "valid"


class ValidationPipeline:
    """Runs every stage in order, recording per-stage timing and notes."""

    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        stages: Optional[List[Any]] = None,
    ) -> None:
        self.config = config or default_config
        self.stages: List[Any] = stages or [
            LocationValidationStage(),
            MetadataValidationStage(),
            ImageValidationStage(),
            DuplicateDetectionStage(),
            SuspiciousDetectionStage(),
            ConfidenceStage(),
        ]

    async def run(
        self,
        payload: Dict[str, Any],
        db: Optional[AsyncSession] = None,
        now: Optional[datetime] = None,
    ) -> PipelineResult:
        """Execute the whole pipeline against a payload."""
        if now is None:
            now = datetime.now(timezone.utc)
        context = StageContext(payload=payload, db=db, config=self.config, now=now)

        start = time.perf_counter()
        for stage in self.stages:
            result = await stage.timed_run(context)  # type: ignore[attr-defined]
            context.results[stage.name] = result

        total_ms = (time.perf_counter() - start) * 1000.0

        notes: List[str] = []
        for result in context.results.values():
            for warn in getattr(result, "warnings", []) or []:
                notes.append(f"[{result.__class__.__name__}] {warn}")
            for reason in getattr(result, "reasons", []) or []:
                notes.append(f"[{result.__class__.__name__}] {reason}")

        pipeline_result = PipelineResult(
            location=context.results["location"],
            metadata=context.results["metadata"],
            image=context.results["image"],
            duplicate=context.results["duplicate"],
            suspicious=context.results["suspicious"],
            confidence=context.results["confidence"],
            stage_times=dict(context.stage_times),
            validation_notes=notes,
        )

        log_stage(
            "pipeline",
            "finished",
            total_ms,
            valid=pipeline_result.valid,
            confidence=pipeline_result.confidence.confidence_score,
            duplicate=pipeline_result.duplicate.duplicate,
            suspicious=pipeline_result.suspicious.suspicious,
        )
        logging.getLogger("business_twin_ai.disaster.validation").info(
            "Validation pipeline total: %.2fms (location=%.2f metadata=%.2f image=%.2f "
            "duplicate=%.2f suspicious=%.2f confidence=%.2f)",
            total_ms,
            pipeline_result.stage_times.get("location", 0.0),
            pipeline_result.stage_times.get("metadata", 0.0),
            pipeline_result.stage_times.get("image", 0.0),
            pipeline_result.stage_times.get("duplicate", 0.0),
            pipeline_result.stage_times.get("suspicious", 0.0),
            pipeline_result.stage_times.get("confidence", 0.0),
        )
        return pipeline_result
