"""Unit tests for backend.app.rules.iphone.IPhoneRawRule — README §11, see
specs/2026-08-07-phase-9-video-iphone-raw-rules/plan.md and validation.md.
"""

from __future__ import annotations

from backend.app.models.media_file import MediaFile
from backend.app.rules.engine import resolve_routing_group
from backend.app.rules.iphone import IPhoneRawRule

rule = IPhoneRawRule()


def _media(extension: str = ".dng", file_type: str | None = "DNG") -> MediaFile:
    return MediaFile(
        scan_id=1,
        absolute_path=f"a{extension}",
        relative_path=f"a{extension}",
        file_name=f"a{extension}",
        extension=extension,
        file_type=file_type,
        media_kind="image",
        size_bytes=1,
        processing_status="pending",
    )


def test_readme_11_dng_with_apple_iphone_signals_matches() -> None:
    metadata = {"Make": "Apple", "Model": "iPhone 15 Pro Max", "FileType": "DNG"}
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.98
    assert result.label == "iphone_camera"
    assert "FileType=DNG" in result.reasons


def test_dng_extension_without_exiftool_file_type_still_matches() -> None:
    media = _media(extension=".dng", file_type=None)
    metadata = {"Make": "Apple", "Model": "iPhone 14 Pro"}
    result = rule.evaluate(media, metadata)
    assert result.score == 0.98


def test_readme_11_non_apple_dng_does_not_nominate_iphone_raw() -> None:
    metadata = {"Make": "Canon", "Model": "EOS 5D", "FileType": "DNG"}
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.0


def test_dng_without_any_make_model_does_not_nominate_iphone_raw() -> None:
    result = rule.evaluate(_media(), {"FileType": "DNG"})
    assert result.score == 0.0


def test_non_dng_image_with_apple_signals_does_not_match() -> None:
    media = _media(extension=".jpg", file_type="JPEG")
    metadata = {"Make": "Apple", "Model": "iPhone 15 Pro Max"}
    result = rule.evaluate(media, metadata)
    assert result.score == 0.0


def test_non_apple_dng_falls_through_to_other_via_resolver() -> None:
    metadata = {"Make": "Canon", "Model": "EOS 5D", "FileType": "DNG"}
    result = rule.evaluate(_media(), metadata)
    candidates = {}
    if result.score > 0:
        candidates[rule.routing_group] = result

    group, winner = resolve_routing_group(candidates)
    assert group == "other"
    assert winner is None
