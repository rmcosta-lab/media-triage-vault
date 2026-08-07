"""Screenshot rule — README §13 "Regras para identificar captura de tela de celular",
roadmap Phase 10.

README §13.3's safety rule ("Somente dimensões ou orientação vertical não
são suficientes") is enforced explicitly, not just via weight tuning: a
result needs a format or metadata-absence anchor signal before geometry
signals count for anything.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from backend.app.rules.engine import RuleResult

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

NAME_PATTERNS = [
    re.compile(r"^Screenshot[_ -]", re.IGNORECASE),
    re.compile(r"^Screen Shot[_ -]", re.IGNORECASE),
    re.compile(r"^Captura de Tela[_ -]", re.IGNORECASE),
    re.compile(r"^Screenshot_\d{8}", re.IGNORECASE),
]

STRONG_NAME_SCORE = 0.90
AUTO_CLASSIFY_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60

_FORMAT_SIGNAL_SCORE = 0.25
_METADATA_ABSENT_SIGNAL_SCORE = 0.20
_VERTICAL_SIGNAL_SCORE = 0.15
_ASPECT_SIGNAL_SCORE = 0.15

_SCREENSHOT_FILE_TYPES = frozenset({"PNG", "HEIC", "HEIF"})
_PHONE_ASPECT_MIN = 0.40
_PHONE_ASPECT_MAX = 0.75


def _name_matches(file_name: str) -> bool:
    return any(pattern.match(file_name) for pattern in NAME_PATTERNS)


def _is_png_or_heif(media: MediaFile, metadata: dict[str, Any]) -> bool:
    file_type = str(media.file_type or metadata.get("FileType") or "").upper()
    return file_type in _SCREENSHOT_FILE_TYPES


def _camera_metadata_absent(metadata: dict[str, Any]) -> bool:
    return not metadata.get("Make")


def _is_vertical(media: MediaFile) -> bool:
    return media.width is not None and media.height is not None and media.height > media.width


def _has_phone_aspect_ratio(media: MediaFile) -> bool:
    if not media.width or not media.height or media.height <= media.width:
        return False
    ratio = media.width / media.height
    return _PHONE_ASPECT_MIN <= ratio <= _PHONE_ASPECT_MAX


class ScreenshotRule:
    name = "screenshot"
    routing_group = "mobile_screenshot"

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult:
        if _name_matches(media.file_name):
            return RuleResult(
                label="mobile_screenshot",
                score=STRONG_NAME_SCORE,
                reasons=[f"File name matches a screenshot pattern ({media.file_name})"],
            )

        format_signal = _is_png_or_heif(media, metadata)
        metadata_absent_signal = _camera_metadata_absent(metadata)

        if not format_signal and not metadata_absent_signal:
            return RuleResult(
                label="unknown",
                score=0.0,
                reasons=[
                    "Only dimensions/orientation signals present without a format "
                    "or metadata-absence anchor; not sufficient alone (README §13.3)."
                ],
            )

        reasons: list[str] = []
        score = 0.0
        if format_signal:
            score += _FORMAT_SIGNAL_SCORE
            reasons.append(f"Format is PNG/HEIF ({media.file_type or metadata.get('FileType')})")
        if metadata_absent_signal:
            score += _METADATA_ABSENT_SIGNAL_SCORE
            reasons.append("Camera metadata (Make) absent")
        if _is_vertical(media):
            score += _VERTICAL_SIGNAL_SCORE
            reasons.append(f"Vertical orientation ({media.width}x{media.height})")
        if _has_phone_aspect_ratio(media):
            score += _ASPECT_SIGNAL_SCORE
            reasons.append("Aspect ratio compatible with a smartphone screen")

        if score < REVIEW_THRESHOLD:
            return RuleResult(
                label="unknown",
                score=0.0,
                reasons=[
                    *reasons,
                    f"Combined medium-signal score {score:.2f} is below the "
                    f"{REVIEW_THRESHOLD} classification floor (README §13.4).",
                ],
            )

        return RuleResult(label="mobile_screenshot", score=min(score, 1.0), reasons=reasons)
