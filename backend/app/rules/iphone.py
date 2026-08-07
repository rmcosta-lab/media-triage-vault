"""iPhone + iPhone RAW rules — README §10-11, roadmap Phase 9.

Neither rule reads ``media.file_name``/``media.extension`` as a positive
signal for "this came from an iPhone" — README §10.3/§10.4 are explicit
that filename pattern or visual similarity alone must never produce a
match; an edited/exported photo that lost its ``Make``/``Model`` stays
unclassified rather than being guessed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from backend.app.rules.engine import RuleResult

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

HIGH_CONFIDENCE = 0.98
_SECONDARY_SIGNAL_SCORES = {1: 0.55, 2: 0.70, 3: 0.85}
_MAX_SECONDARY_SCORE = _SECONDARY_SIGNAL_SCORES[max(_SECONDARY_SIGNAL_SCORES)]

# Sign-prefixed lat/long pair, e.g. "+35.6762+139.6503/" — README §10.2 "ISO 6709".
_ISO_6709_PATTERN = re.compile(r"^[+-]\d+(\.\d+)?[+-]\d+(\.\d+)?")

_DNG_FILE_TYPE = "DNG"


def _is_apple_make_and_iphone_model(metadata: dict[str, Any]) -> bool:
    make = metadata.get("Make")
    model = metadata.get("Model")
    return make == "Apple" and isinstance(model, str) and model.startswith("iPhone")


def _count_secondary_signals(metadata: dict[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []

    software = metadata.get("Software")
    if isinstance(software, str) and ("iphone" in software.lower() or "ios" in software.lower()):
        reasons.append(f"QuickTime Software mentions iPhone/iOS ({software})")

    encoder = metadata.get("Encoder") or metadata.get("CompressorName")
    if isinstance(encoder, str) and "apple" in encoder.lower():
        reasons.append(f"QuickTime Encoder/CompressorName mentions Apple ({encoder})")

    handler = metadata.get("HandlerDescription")
    if isinstance(handler, str) and ("apple" in handler.lower() or "core media" in handler.lower()):
        reasons.append(f"QuickTime HandlerDescription mentions Apple ({handler})")

    location = metadata.get("LocationInformation")
    if isinstance(location, str) and _ISO_6709_PATTERN.match(location):
        reasons.append(f"LocationInformation present in ISO 6709 format ({location})")

    return len(reasons), reasons


def _is_dng(media: MediaFile, metadata: dict[str, Any]) -> bool:
    file_type = media.file_type or metadata.get("FileType")
    if file_type and str(file_type).upper() == _DNG_FILE_TYPE:
        return True
    extension = (media.extension or "").lower()
    return extension == ".dng"


class IPhoneRule:
    name = "iphone"
    routing_group = "iphone_photo"

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult:
        if _is_apple_make_and_iphone_model(metadata):
            return RuleResult(
                label="iphone_camera",
                score=HIGH_CONFIDENCE,
                reasons=[
                    f"EXIF Make={metadata.get('Make')}",
                    f"EXIF Model={metadata.get('Model')}",
                ],
            )

        signal_count, reasons = _count_secondary_signals(metadata)
        if signal_count == 0:
            return RuleResult(
                label="unknown",
                score=0.0,
                reasons=[
                    "No Make/Model or QuickTime Apple signals found; filename alone "
                    "is not sufficient to identify an iPhone (README §10.3/§10.4)."
                ],
            )

        score = _SECONDARY_SIGNAL_SCORES.get(signal_count, _MAX_SECONDARY_SCORE)
        return RuleResult(label="iphone_camera", score=score, reasons=reasons)


class IPhoneRawRule:
    name = "iphone_raw"
    routing_group = "iphone_raw"

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult:
        if not _is_dng(media, metadata):
            return RuleResult(label="unknown", score=0.0, reasons=["Not a DNG file."])

        if not _is_apple_make_and_iphone_model(metadata):
            return RuleResult(
                label="other_camera",
                score=0.0,
                reasons=[
                    "DNG file but Make/Model do not indicate iPhone; "
                    'routes to "other" (README §11).'
                ],
            )

        return RuleResult(
            label="iphone_camera",
            score=HIGH_CONFIDENCE,
            reasons=[
                "FileType=DNG",
                f"EXIF Make={metadata.get('Make')}",
                f"EXIF Model={metadata.get('Model')}",
            ],
        )
