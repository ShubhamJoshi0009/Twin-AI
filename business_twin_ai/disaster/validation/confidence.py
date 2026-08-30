"""Confidence scoring stage (spec §7)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin


@dataclass
class ConfidenceResult:
    """Result of confidence scoring."""

    confidence_score: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)


class ConfidenceStage(TimedStageMixin):
    """Compute the weighted overall confidence for a report.

    Weights (spec §7): location 30%, metadata 20%, image 20%, duplicate 15%,
    reporter trust 15%. The duplicate component is inverted (a high duplicate
    score *lowers* confidence), and the reporter trust score comes from the
    reporter profile (injected into the payload by the service).
    """

    name = "confidence"

    async def run(self, context: StageContext) -> ConfidenceResult:
        cfg: ValidationConfig = context.config

        location = context.results.get("location")
        metadata = context.results.get("metadata")
        image = context.results.get("image")
        duplicate = context.results.get("duplicate")

        location_score = location.location_score if location else 0.0
        metadata_score = metadata.metadata_score if metadata else 0.0
        image_score = image.image_score if image else cfg.IMAGE_NO_IMAGE_SCORE

        dup_component = 100.0
        if duplicate is not None:
            dup_component = 100.0 - duplicate.duplicate_score

        trust_score = float(context.payload.get("_reporter_trust", cfg.TRUST_START))

        raw = (
            cfg.CONF_W_LOCATION * location_score
            + cfg.CONF_W_METADATA * metadata_score
            + cfg.CONF_W_IMAGE * image_score
            + cfg.CONF_W_DUPLICATE * dup_component
            + cfg.CONF_W_TRUST * trust_score
        )
        confidence = round(max(0.0, min(100.0, raw)), 2)

        return ConfidenceResult(
            confidence_score=confidence,
            components={
                "location": round(location_score, 2),
                "metadata": round(metadata_score, 2),
                "image": round(image_score, 2),
                "duplicate": round(dup_component, 2),
                "trust": round(trust_score, 2),
            },
        )
