"""Unit tests for backend.app.rules.screenshot — README §13, see
specs/2026-08-07-phase-10-whatsapp-screenshot-rules/plan.md and validation.md.
"""

from __future__ import annotations

import pytest

from backend.app.models.media_file import MediaFile
from backend.app.rules.engine import RuleResult, build_classification_result
from backend.app.rules.screenshot import AUTO_CLASSIFY_THRESHOLD, ScreenshotRule

rule = ScreenshotRule()


def _media(
    file_name: str = "photo.png",
    file_type: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> MediaFile:
    return MediaFile(
        scan_id=1,
        absolute_path=file_name,
        relative_path=file_name,
        file_name=file_name,
        extension="." + file_name.rsplit(".", 1)[-1],
        file_type=file_type,
        width=width,
        height=height,
        size_bytes=1,
        processing_status="pending",
    )


@pytest.mark.parametrize(
    "file_name",
    [
        "Screenshot_20260730-152000.png",
        "Screenshot 2026-07-30.png",
        "Screen Shot 2026-07-30 at 15.20.00.png",
        "Captura de Tela_2026-07-30.png",
    ],
)
def test_readme_13_1_name_patterns_score_090(file_name: str) -> None:
    result = rule.evaluate(_media(file_name), {})
    assert result.score == 0.90
    assert result.label == "mobile_screenshot"


def test_readme_13_3_safety_rule_geometry_only_does_not_classify() -> None:
    media = _media(file_name="random.jpg", file_type="JPEG", width=1080, height=1920)
    result = rule.evaluate(media, {"Make": "Apple"})
    assert result.score == 0.0
    assert result.label == "unknown"


def test_all_four_medium_signals_land_in_review_band() -> None:
    media = _media(file_name="random.png", file_type="PNG", width=1080, height=1920)
    result = rule.evaluate(media, {})
    assert result.score == 0.75
    assert result.label == "mobile_screenshot"
    assert result.score < AUTO_CLASSIFY_THRESHOLD


def test_two_signals_below_floor_does_not_classify() -> None:
    media = _media(file_name="random.png", file_type="PNG", width=None, height=None)
    result = rule.evaluate(media, {})
    assert result.score == 0.0
    assert result.label == "unknown"


def test_three_signals_at_exact_classification_floor() -> None:
    # width/height ratio (500/1500 = 0.33) falls outside the phone-aspect
    # band, so only format + metadata-absent + vertical contribute.
    media = _media(file_name="random.png", file_type="PNG", width=500, height=1500)
    result = rule.evaluate(media, {})
    assert result.score == pytest.approx(0.60)
    assert result.label == "mobile_screenshot"


def test_confidence_bands_drive_requires_review_end_to_end() -> None:
    auto = build_classification_result(
        media_kind="image",
        image_format="standard",
        candidates={"mobile_screenshot": RuleResult(label="mobile_screenshot", score=0.90)},
        review_threshold=AUTO_CLASSIFY_THRESHOLD,
    )
    review_band = build_classification_result(
        media_kind="image",
        image_format="standard",
        candidates={"mobile_screenshot": RuleResult(label="mobile_screenshot", score=0.75)},
        review_threshold=AUTO_CLASSIFY_THRESHOLD,
    )
    lower_review_band = build_classification_result(
        media_kind="image",
        image_format="standard",
        candidates={"mobile_screenshot": RuleResult(label="mobile_screenshot", score=0.65)},
        review_threshold=AUTO_CLASSIFY_THRESHOLD,
    )

    assert auto.requires_review is False
    assert review_band.requires_review is True
    assert lower_review_band.requires_review is True
