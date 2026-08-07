"""WhatsApp rule — README §12 "Regras para identificar arquivos do WhatsApp", roadmap Phase 10.

Identification is probabilistic (README §12): absent camera metadata is
only ever a bonus on top of a name/directory signal, never sufficient on
its own (§12.3's "Apenas metadados ausentes: não classificar", §12.4).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from backend.app.rules.engine import RuleResult

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

NAME_PATTERNS = [
    re.compile(r"^IMG-\d{8}-WA\d+\.(jpg|jpeg|png|heic)$", re.IGNORECASE),
    re.compile(r"^VID-\d{8}-WA\d+\.(mp4|mov|m4v)$", re.IGNORECASE),
    re.compile(r"^WhatsApp Image .+\.(jpg|jpeg|png)$", re.IGNORECASE),
    re.compile(r"^WhatsApp Video .+\.(mp4|mov)$", re.IGNORECASE),
]

NAME_MATCH_SCORE = 0.65
DIRECTORY_MATCH_SCORE = 0.45
METADATA_ABSENT_SCORE = 0.10
MAX_SCORE = 1.00


def _directory_segments(relative_path: str) -> list[str]:
    normalized = relative_path.replace("\\", "/")
    return normalized.split("/")[:-1]


def _name_matches(file_name: str) -> bool:
    return any(pattern.match(file_name) for pattern in NAME_PATTERNS)


def _directory_has_whatsapp(segments: list[str]) -> bool:
    return any("whatsapp" in segment.lower() for segment in segments)


def _directory_has_sent(segments: list[str]) -> bool:
    return any(segment.lower() == "sent" for segment in segments)


def _camera_metadata_absent(metadata: dict[str, Any]) -> bool:
    return not metadata.get("Make")


class WhatsAppRule:
    name = "whatsapp"
    routing_group = "whatsapp_received"

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult:
        segments = _directory_segments(media.relative_path)
        name_matches = _name_matches(media.file_name)
        directory_matches = _directory_has_whatsapp(segments)
        metadata_absent = _camera_metadata_absent(metadata)

        if not name_matches and not directory_matches:
            reason = (
                "Camera metadata alone is absent; that alone does not indicate "
                "WhatsApp (README §12.4)."
                if metadata_absent
                else "No WhatsApp name or directory signal found."
            )
            return RuleResult(label="unknown", score=0.0, reasons=[reason])

        score = 0.0
        reasons: list[str] = []
        if name_matches:
            score += NAME_MATCH_SCORE
            reasons.append(f"File name matches a WhatsApp pattern ({media.file_name})")
        if directory_matches:
            score += DIRECTORY_MATCH_SCORE
            reasons.append('Directory path contains "WhatsApp"')
        if metadata_absent:
            score += METADATA_ABSENT_SCORE
            reasons.append("Camera metadata (Make) absent")
        score = min(score, MAX_SCORE)

        if _directory_has_sent(segments):
            label = "whatsapp_sent"
            reasons.append('Directory path contains a "Sent" folder')
        else:
            label = "whatsapp_received"

        return RuleResult(label=label, score=score, reasons=reasons)
