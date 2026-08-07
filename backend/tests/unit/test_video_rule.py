"""Unit tests for backend.app.rules.video — README §9, see
specs/2026-08-07-phase-9-video-iphone-raw-rules/plan.md and validation.md.
"""

from __future__ import annotations

from backend.app.models.media_file import MediaFile
from backend.app.rules.video import VideoRule

rule = VideoRule()


def _media(**overrides: object) -> MediaFile:
    defaults: dict[str, object] = {
        "scan_id": 1,
        "absolute_path": "a.mp4",
        "relative_path": "a.mp4",
        "file_name": "a.mp4",
        "extension": ".mp4",
        "size_bytes": 1,
        "processing_status": "pending",
    }
    defaults.update(overrides)
    return MediaFile(**defaults)


def test_video_rule_fires_on_mime_type_alone() -> None:
    media = _media(mime_type="video/mp4", file_type=None, media_kind=None)
    result = rule.evaluate(media, {})
    assert result.score == 1.0
    assert result.label == "video"
    assert any("MIME" in reason for reason in result.reasons)


def test_video_rule_fires_on_exiftool_file_type_alone() -> None:
    media = _media(mime_type=None, file_type="MOV", media_kind=None)
    result = rule.evaluate(media, {})
    assert result.score == 1.0
    assert any("FileType" in reason for reason in result.reasons)


def test_video_rule_fires_on_media_kind_alone() -> None:
    media = _media(mime_type=None, file_type=None, media_kind="video")
    result = rule.evaluate(media, {})
    assert result.score == 1.0
    assert any("media_kind" in reason for reason in result.reasons)


def test_video_rule_fires_for_corrupted_but_still_video_file() -> None:
    media = _media(
        mime_type=None,
        file_type=None,
        media_kind="video",
        processing_status="error",
        error_code="VIDEO_UNREADABLE",
    )
    result = rule.evaluate(media, {})
    assert result.score == 1.0


def test_video_rule_scores_zero_for_non_video_image() -> None:
    media = _media(extension=".jpg", mime_type="image/jpeg", file_type="JPEG", media_kind="image")
    result = rule.evaluate(media, {})
    assert result.score == 0.0
    assert result.reasons
