"""Video rule — README §9 "Regras para identificar vídeos", roadmap Phase 9.

By the time classification runs, Phase 5 (extension + MIME + signature)
and Phase 6 (ExifTool `FileType` correction + FFprobe stream validation)
have already combined all three of README §9's signals into
``MediaFile.media_kind``/``file_type``/``mime_type``. This rule reads that
output rather than re-invoking FFprobe itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.app.rules.engine import RuleResult

if TYPE_CHECKING:
    from backend.app.models.media_file import MediaFile

_VIDEO_FILE_TYPES = frozenset({"MP4", "MOV", "M4V", "3GP", "AVI", "MKV", "WEBM", "3G2", "QT"})


class VideoRule:
    name = "video"
    routing_group = "video"

    def evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult:
        reasons: list[str] = []

        mime_type = media.mime_type or metadata.get("MIMEType")
        if mime_type and str(mime_type).startswith("video/"):
            reasons.append(f"MIME type starts with video/ ({mime_type})")

        file_type = media.file_type or metadata.get("FileType")
        if file_type and str(file_type).upper() in _VIDEO_FILE_TYPES:
            reasons.append(f"ExifTool FileType indicates video ({file_type})")

        if media.media_kind == "video" and not reasons:
            reasons.append("media_kind=video (FFprobe validated a video stream in Phase 6)")

        if not reasons:
            return RuleResult(
                label="video",
                score=0.0,
                reasons=[
                    "No video signal: MIME type, ExifTool FileType, and media_kind all disagree."
                ],
            )

        return RuleResult(label="video", score=1.0, reasons=reasons)
