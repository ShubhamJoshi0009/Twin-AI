"""Pure-Python image inspection for the disaster validation layer.

No Pillow / external imaging dependency. Supports format sniffing, dimension
parsing (PNG / JPEG / GIF / WebP / BMP), SHA-256 hashing, EXIF GPS + timestamp
extraction for JPEG, and basic corruption detection.

The module is deliberately dependency-free so the validation pipeline stays
fast and portable. Swap in Pillow later by replacing ``inspect_image``.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

_SUPPORTED_FORMATS = ("jpeg", "png", "gif", "webp", "bmp")


@dataclass
class ImageInspection:
    """Result of inspecting a raw image byte blob."""

    present: bool = False
    valid: bool = False
    format: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int = 0
    sha256: Optional[str] = None
    gps: Optional[Tuple[float, float]] = None  # (lat, lon) when EXIF GPS present
    timestamp: Optional[str] = None  # EXIF DateTimeOriginal when present
    corruption_reason: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def detect_format(data: bytes) -> Optional[str]:
    """Sniff image format from magic bytes; None when unrecognised."""
    if data[:2] == b"\xff\xd8":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    return None


def _png_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Read width/height from the PNG IHDR chunk (big-endian)."""
    if len(data) < 24:
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Scan JPEG segments for an SOF marker to read dimensions."""
    i = 2
    length = len(data)
    while i + 9 < length:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # Standalone markers / SOS / EOI terminate the scan or carry no size.
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker in (0xD9, 0xDA):
            break
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        i += 2 + seg_len
    return None


def _gif_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Read width/height from the GIF logical screen descriptor (little-endian)."""
    if len(data) < 10:
        return None
    width, height = struct.unpack("<HH", data[6:10])
    return width, height


def _webp_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Parse WebP dimensions from VP8 / VP8L / VP8X chunks."""
    if len(data) < 30:
        return None
    fourcc = data[12:16]
    if fourcc == b"VP8X":
        # 24-bit LE width-1 / height-1 at offset 24 / 27
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    if fourcc == b"VP8L":
        bits = int.from_bytes(data[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if fourcc == b"VP8 ":
        # 14-bit LE width/height after a 3-byte frame tag
        width = struct.unpack("<H", data[26:28])[0] & 0x3FFF
        height = struct.unpack("<H", data[28:30])[0] & 0x3FFF
        return width, height
    return None


def _bmp_dimensions(data: bytes) -> Optional[Tuple[int, int]]:
    """Read width/height from the BMP DIB header."""
    if len(data) < 26:
        return None
    width = struct.unpack("<i", data[18:22])[0]
    height = abs(struct.unpack("<i", data[22:26])[0])
    return width, height


def dimensions_for(data: bytes, fmt: str) -> Optional[Tuple[int, int]]:
    """Dispatch dimension parsing based on the sniffed format."""
    if fmt == "png":
        return _png_dimensions(data)
    if fmt == "jpeg":
        return _jpeg_dimensions(data)
    if fmt == "gif":
        return _gif_dimensions(data)
    if fmt == "webp":
        return _webp_dimensions(data)
    if fmt == "bmp":
        return _bmp_dimensions(data)
    return None


# ── EXIF (JPEG APP1) parsing ────────────────────────────────────────────────
# Minimal but correct TIFF/EXIF walker. Only tags we care about are resolved:
#   0x010F / 0x0110  -> Make / Model (informational)
#   0x0132           -> DateTime
#   0x9003           -> DateTimeOriginal
#   0x8825           -> GPS IFD pointer
#   0x8825 / 0x8825  -> (GPS IFD entry)
# GPS IFD: 1=lat ref, 2=lat (3 rationals), 3=lon ref, 4=lon (3 rationals).

_EXIF_DATETIME_TAGS = (0x0132, 0x9003)


def _exif_value(data: bytes, endian: str, entry_offset: int, type_id: int, count: int) -> object:
    """Read an EXIF IFD entry value, handling inline vs offset storage.

    Returns ``None`` for truncated/out-of-range values instead of raising —
    malformed EXIF must degrade to a corruption flag, never a crash.
    """
    value_field = entry_offset + 8
    type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
    size = type_sizes.get(type_id, 1) * count
    if value_field + 4 > len(data):
        return None
    if size <= 4:
        raw = data[value_field : value_field + 4]
    else:
        offset = struct.unpack(endian + "I", data[value_field : value_field + 4])[0]
        raw = data[offset : offset + size]
    if type_id == 2:  # ASCII
        return raw.split(b"\x00")[0].decode("ascii", "ignore")
    if type_id in (3, 4, 9):  # SHORT / LONG / SLONG
        if len(raw) < 4 * count:
            return None
        values = struct.unpack(endian + "I" * count, raw[: 4 * count])
        return values[0] if count == 1 else values
    if type_id in (5, 10):  # RATIONAL / SRATIONAL
        values: List[float] = []
        for i in range(count):
            chunk = raw[i * 8 : i * 8 + 8]
            if len(chunk) < 8:
                return None
            num, den = struct.unpack(endian + "II", chunk)
            values.append(num / den if den else 0.0)
        return tuple(values)
    return None


def _walk_ifd(
    data: bytes, endian: str, ifd_offset: int, wanted: set
) -> Dict[int, object]:
    """Walk an IFD at ifd_offset and return {tag: value} for wanted tags."""
    if ifd_offset + 2 > len(data):
        return {}
    (count,) = struct.unpack(endian + "H", data[ifd_offset : ifd_offset + 2])
    results: Dict[int, object] = {}
    for i in range(count):
        entry = ifd_offset + 2 + i * 12
        if entry + 12 > len(data):
            break
        tag, type_id, entry_count = struct.unpack(
            endian + "HHI", data[entry : entry + 8]
        )
        if tag in wanted:
            results[tag] = _exif_value(data, endian, entry, type_id, entry_count)
    return results


def _parse_jpeg_exif(data: bytes) -> Dict:
    """Extract GPS + DateTime metadata from a JPEG APP1 EXIF segment."""
    result: Dict = {"gps": None, "timestamp": None, "make": None, "model": None}
    i = 2
    length = len(data)
    while i + 4 < length:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker in (0xD9, 0xDA):
            break
        seg_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
        if marker == 0xE1 and data[i + 4 : i + 10] == b"Exif\x00\x00":
            tiff = data[i + 10 : i + 2 + seg_len]
            result.update(_parse_tiff(tiff))
            return result
        i += 2 + seg_len
    return result


def _parse_tiff(tiff: bytes) -> Dict:
    """Parse a TIFF block (after the 'Exif\\0\\0' marker) for GPS + datetime."""
    out: Dict = {"gps": None, "timestamp": None, "make": None, "model": None}
    if len(tiff) < 8:
        return out
    endian = "<" if tiff[:2] == b"II" else ">" if tiff[:2] == b"MM" else None
    if endian is None:
        return out
    if struct.unpack(endian + "H", tiff[2:4])[0] != 0x2A:
        return out
    ifd_offset = struct.unpack(endian + "I", tiff[4:8])[0]

    ifd0 = _walk_ifd(tiff, endian, ifd_offset, {0x010F, 0x0110, 0x0132, 0x8769, 0x8825})
    out["make"] = ifd0.get(0x010F)
    out["model"] = ifd0.get(0x0110)
    out["timestamp"] = ifd0.get(0x0132) or out["timestamp"]

    gps_ifd = ifd0.get(0x8825)
    if isinstance(gps_ifd, int):
        gps_tags = _walk_ifd(tiff, endian, gps_ifd, {1, 2, 3, 4})
        out["gps"] = _gps_from_tags(gps_tags)

    exif_ifd = ifd0.get(0x8769)
    if isinstance(exif_ifd, int):
        exif_tags = _walk_ifd(tiff, endian, exif_ifd, set(_EXIF_DATETIME_TAGS))
        for tag in _EXIF_DATETIME_TAGS:
            if exif_tags.get(tag):
                out["timestamp"] = exif_tags[tag]
                break
    return out


def _gps_from_tags(tags: Dict[int, object]) -> Optional[Tuple[float, float]]:
    """Convert GPS IFD tags (ref + rationals) into a (lat, lon) tuple."""
    lat_ref = tags.get(1)
    lat_vals = tags.get(2)
    lon_ref = tags.get(3)
    lon_vals = tags.get(4)
    if not (isinstance(lat_vals, tuple) and isinstance(lon_vals, tuple)):
        return None
    if len(lat_vals) < 3 or len(lon_vals) < 3:
        return None

    def _to_degrees(parts: Tuple[float, ...]) -> float:
        return parts[0] + parts[1] / 60.0 + parts[2] / 3600.0

    lat = _to_degrees(lat_vals)
    lon = _to_degrees(lon_vals)
    if str(lat_ref).upper().startswith("S"):
        lat = -lat
    if str(lon_ref).upper().startswith("W"):
        lon = -lon
    return lat, lon


def inspect_image(data: bytes) -> ImageInspection:
    """Full inspection of raw image bytes (format, dims, hash, EXIF, corruption)."""
    inspection = ImageInspection(present=bool(data), size_bytes=len(data))
    if not data:
        return inspection

    inspection.sha256 = sha256_hex(data)
    fmt = detect_format(data)
    if fmt is None:
        inspection.corruption_reason = "unrecognized format"
        return inspection
    inspection.format = fmt
    inspection.valid = fmt in _SUPPORTED_FORMATS

    # EXIF (JPEG) is parsed even when dimensions are unreadable — a truncated
    # header must not hide GPS/timestamp metadata that may still be present.
    if fmt == "jpeg":
        try:
            exif = _parse_jpeg_exif(data)
            inspection.gps = exif.get("gps")
            inspection.timestamp = exif.get("timestamp")
            inspection.metadata = {
                "make": exif.get("make"),
                "model": exif.get("model"),
            }
        except struct.error:
            inspection.corruption_reason = "malformed EXIF segment"

    dims = dimensions_for(data, fmt)
    if dims is None:
        inspection.corruption_reason = "unable to read dimensions (truncated?)"
        return inspection
    inspection.width, inspection.height = dims
    if inspection.width <= 0 or inspection.height <= 0:
        inspection.corruption_reason = "non-positive dimensions"
        return inspection

    inspection.valid = True
    return inspection
