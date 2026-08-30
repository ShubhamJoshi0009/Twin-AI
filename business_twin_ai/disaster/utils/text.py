"""Text heuristics: similarity, spam words, repeated characters."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Tuple

_SPACES_RE = re.compile(r"\s+")
_REPEAT_RE = re.compile(r"(.)\1{%d,}" % 3)  # 4+ identical characters in a row


def normalize(text: str) -> str:
    """Lowercase, strip, and collapse whitespace for comparison."""
    return _SPACES_RE.sub(" ", (text or "").strip().lower())


def text_similarity(a: str, b: str) -> float:
    """Similarity 0.0-1.0 between two free-text strings (SequenceMatcher)."""
    na, nb = normalize(a), normalize(b)
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def repeated_char_ratio(text: str) -> float:
    """Fraction of the string consumed by long runs of a single character."""
    if not text:
        return 0.0
    norm = normalize(text)
    runs = sum(len(m.group(0)) for m in _REPEAT_RE.finditer(norm))
    return min(1.0, runs / max(1, len(norm)))


def find_spam_words(text: str, spam_words: Tuple[str, ...]) -> List[str]:
    """Return the spam phrases found in the text (case-insensitive)."""
    lowered = (text or "").lower()
    return [w for w in spam_words if w in lowered]


def truncate(text: str, limit: int) -> str:
    """Truncate text for similarity comparisons (perf guard)."""
    return text[:limit] if text else ""
