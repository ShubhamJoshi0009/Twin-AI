"""Image validation stage (spec §3).

A missing image never rejects the report — it only reduces confidence. When an
image is provided we sniff its format, read dimensions, hash it, look for EXIF
GPS/timestamp (JPEG), and flag corruption.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from business_twin_ai.disaster.config import ValidationConfig
from business_twin_ai.disaster.utils.images import inspect_image
from business_twin_ai.disaster.validation.base import StageContext, TimedStageMixin


@dataclass
class ImageResult:
    """Result of image validation."""

    image_valid: bool = True
    image_score: float = 50.0  # neutral score when no image
    image_metadata: Dict[str, Any] = field(default_factory=dict)
    image_hash: Optional[str] = None
    present: bool = False
    warnings: list = field(default_factory=list)


def decode_base64_image(raw: str) -> Optional[bytes]:
    """Decode a base64 (optionally data-URI) image string into bytes."""
    if not raw:
        return None
    data = raw.strip()
    if data.startswith("data:"):
        _, _, data = data.partition(",")
    try:
        return base64.b64decode(data, validate=True)
    except (ValueError, TypeError):
        return None


class ImageValidationStage(TimedStageMixin):
    """Validate image format, size, dimensions, hash, EXIF and corruption."""

    name = "image"

    async def run(self, context: StageContext) -> ImageResult:
        cfg: ValidationConfig = context.config
        raw = context.payload.get("image_base64")

        # No image → don't reject, just reduce confidence (spec §3).
        if not raw:
            return ImageResult(
                image_valid=True,
                image_score=cfg.IMAGE_NO_IMAGE_SCORE,
                present=False,
                warnings=["no image attached — confidence reduced"],
            )

        data = decode_base64_image(raw)
        if data is None:
            return ImageResult(
                image_valid=False,
                image_score=0.0,
                present=True,
                warnings=["image_base64 could not be decoded"],
            )

        inspection = inspect_image(data)
        warnings: list = []
        score = 100.0

        # Supported format?
        if inspection.format not in cfg.ALLOWED_IMAGE_FORMATS:
            score -= 40.0
            warnings.append(f"unsupported format: {inspection.format}")
        # Size bounds?
        if len(data) > cfg.MAX_IMAGE_BYTES:
            score -= 20.0
            warnings.append("image exceeds maximum size")
        elif len(data) < cfg.MIN_IMAGE_BYTES:
            score -= 5.0
            warnings.append("image is suspiciously tiny")
        # Dimensions / corruption?
        if inspection.corruption_reason:
            score -= 35.0
            warnings.append(f"corruption detected: {inspection.corruption_reason}")
        else:
            if inspection.width and inspection.width > cfg.MAX_IMAGE_DIMENSION:
                score -= 10.0
                warnings.append("image width too large")
            if inspection.width and inspection.width < cfg.MIN_IMAGE_DIMENSION:
                score -= 10.0
                warnings.append("image width too small")
        # EXIF GPS / timestamp are nice-to-have, not required.
        if inspection.gps:
            score = min(100.0, score + 5.0)
        if inspection.timestamp:
            score = min(100.0, score + 5.0)

        image_valid = (
            inspection.valid
            and inspection.format in cfg.ALLOWED_IMAGE_FORMATS
            and not inspection.corruption_reason
        )
        return ImageResult(
            image_valid=image_valid,
            image_score=round(max(0.0, min(100.0, score)), 2),
            image_metadata={
                "present": True,
                "format": inspection.format,
                "width": inspection.width,
                "height": inspection.height,
                "size_bytes": len(data),
                "gps": inspection.gps is not None,
                "timestamp": inspection.timestamp is not None,
            },
            image_hash=inspection.sha256,
            present=True,
            warnings=warnings,
        )
