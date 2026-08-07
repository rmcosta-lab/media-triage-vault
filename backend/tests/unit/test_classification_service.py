"""Unit tests for backend.app.services.classification — see
specs/2026-08-07-phase-12-classify-cli-overrides/plan.md and validation.md.
"""

from __future__ import annotations

from backend.app.models.media_file import MediaFile
from backend.app.rules.screenshot import AUTO_CLASSIFY_THRESHOLD
from backend.app.services.classification import (
    _build_candidates,
    _classify_one,
    _determine_image_format,
    _review_threshold_for,
)


def _media(**overrides: object) -> MediaFile:
    defaults: dict[str, object] = {
        "scan_id": 1,
        "absolute_path": "a.jpg",
        "relative_path": "a.jpg",
        "file_name": "a.jpg",
        "extension": ".jpg",
        "size_bytes": 1,
        "processing_status": "pending",
        "media_kind": "image",
    }
    defaults.update(overrides)
    return MediaFile(**defaults)


def test_determine_image_format_video_is_not_applicable() -> None:
    media = _media(media_kind="video", extension=".mp4")
    assert _determine_image_format(media) == "not_applicable"


def test_determine_image_format_dng_extension_is_raw() -> None:
    media = _media(extension=".dng", file_type=None)
    assert _determine_image_format(media) == "raw"


def test_determine_image_format_dng_file_type_is_raw() -> None:
    media = _media(extension=".tif", file_type="DNG")
    assert _determine_image_format(media) == "raw"


def test_determine_image_format_jpeg_is_standard() -> None:
    media = _media(extension=".jpg", file_type="JPEG")
    assert _determine_image_format(media) == "standard"


def test_build_candidates_video_fires_only_video_rule() -> None:
    media = _media(media_kind="video", extension=".mp4", mime_type="video/mp4")
    candidates = _build_candidates(media, {})
    assert set(candidates) == {"video"}


def test_build_candidates_iphone_photo_fires_iphone_rule() -> None:
    media = _media()
    candidates = _build_candidates(media, {"Make": "Apple", "Model": "iPhone 15 Pro Max"})
    assert "iphone_photo" in candidates


def test_build_candidates_no_signal_is_empty() -> None:
    media = _media(file_name="random.jpg")
    candidates = _build_candidates(media, {"Make": "Canon"})
    assert candidates == {}


def test_review_threshold_for_screenshot_uses_auto_classify_threshold() -> None:
    assert _review_threshold_for("mobile_screenshot") == AUTO_CLASSIFY_THRESHOLD


def test_review_threshold_for_other_groups_uses_default() -> None:
    assert _review_threshold_for("video") == 0.60


def test_classify_one_screenshot_medium_band_requires_review() -> None:
    media = _media(
        file_name="random.png", extension=".png", file_type="PNG", width=1080, height=1920
    )
    result = _classify_one(media, {})
    assert result.routing_group == "mobile_screenshot"
    assert result.confidence == 0.75
    assert result.requires_review is True


def test_classify_one_no_candidates_falls_back_to_other() -> None:
    media = _media(file_name="random.jpg", extension=".jpg", file_type="JPEG")
    result = _classify_one(media, {"Make": "Canon"})
    assert result.routing_group == "other"
    assert result.requires_review is True
