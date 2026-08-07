"""Unit tests for backend.app.rules.iphone.IPhoneRule — README §10, see
specs/2026-08-07-phase-9-video-iphone-raw-rules/plan.md and validation.md.
"""

from __future__ import annotations

from backend.app.models.media_file import MediaFile
from backend.app.rules.iphone import IPhoneRule

rule = IPhoneRule()


def _media(file_name: str = "IMG_1234.JPG", extension: str = ".jpg") -> MediaFile:
    return MediaFile(
        scan_id=1,
        absolute_path=file_name,
        relative_path=file_name,
        file_name=file_name,
        extension=extension,
        size_bytes=1,
        processing_status="pending",
    )


def test_readme_10_1_high_confidence_worked_example() -> None:
    metadata = {"Make": "Apple", "Model": "iPhone 15 Pro Max"}
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.98
    assert result.label == "iphone_camera"
    assert "EXIF Make=Apple" in result.reasons
    assert "EXIF Model=iPhone 15 Pro Max" in result.reasons


def test_readme_10_2_single_secondary_signal_is_lower_confidence() -> None:
    metadata = {"HandlerDescription": "Apple Core Media Video"}
    result = rule.evaluate(_media(), metadata)
    assert result.label == "iphone_camera"
    assert result.score == 0.55


def test_readme_10_2_two_secondary_signals_score_higher_than_one() -> None:
    metadata = {
        "HandlerDescription": "Apple Core Media Video",
        "Encoder": "Apple",
    }
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.70


def test_readme_10_2_three_plus_secondary_signals_score_highest_tier() -> None:
    metadata = {
        "HandlerDescription": "Apple Core Media Video",
        "Encoder": "Apple",
        "LocationInformation": "+35.6762+139.6503/",
    }
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.85


def test_readme_10_3_filename_alone_is_capped_at_040() -> None:
    for file_name in ("IMG_1234.JPG", "IMG_1234.MOV"):
        result = rule.evaluate(_media(file_name=file_name), {})
        assert result.score <= 0.40
        assert result.label == "unknown"


def test_readme_10_4_stripped_make_model_does_not_fall_back_to_filename() -> None:
    media = _media(file_name="IMG_1234.JPG")
    result = rule.evaluate(media, {})
    assert result.score == 0.0
    assert result.label == "unknown"


def test_non_apple_make_does_not_match() -> None:
    metadata = {"Make": "Canon", "Model": "EOS R5"}
    result = rule.evaluate(_media(), metadata)
    assert result.score == 0.0
    assert result.label == "unknown"
