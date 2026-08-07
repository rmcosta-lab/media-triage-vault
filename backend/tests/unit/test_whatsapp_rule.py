"""Unit tests for backend.app.rules.whatsapp — README §12, see
specs/2026-08-07-phase-10-whatsapp-screenshot-rules/plan.md and validation.md.
"""

from __future__ import annotations

import pytest

from backend.app.models.media_file import MediaFile
from backend.app.rules.whatsapp import WhatsAppRule

rule = WhatsAppRule()


def _media(file_name: str, relative_path: str | None = None) -> MediaFile:
    path = relative_path if relative_path is not None else file_name
    return MediaFile(
        scan_id=1,
        absolute_path=path,
        relative_path=path,
        file_name=file_name,
        extension="." + file_name.rsplit(".", 1)[-1],
        size_bytes=1,
        processing_status="pending",
    )


@pytest.mark.parametrize(
    "file_name",
    [
        "IMG-20260730-WA0001.jpg",
        "VID-20260730-WA0001.mp4",
        "WhatsApp Image 2026-07-30 at 15.20.00.jpeg",
        "WhatsApp Video 2026-07-30 at 15.20.00.mp4",
    ],
)
def test_readme_12_1_name_patterns_score_065(file_name: str) -> None:
    # Make present so the absent-metadata bonus doesn't add to the isolated
    # name-match score.
    result = rule.evaluate(_media(file_name), {"Make": "Canon"})
    assert result.score == 0.65
    assert result.label == "whatsapp_received"


def test_directory_only_match_scores_045() -> None:
    media = _media("random.jpg", relative_path="WhatsApp Images/random.jpg")
    result = rule.evaluate(media, {"Make": "Canon"})
    assert result.score == 0.45
    assert result.label == "whatsapp_received"


def test_name_and_directory_and_absent_metadata_caps_at_100() -> None:
    media = _media(
        "IMG-20260730-WA0001.jpg", relative_path="Media/WhatsApp Images/IMG-20260730-WA0001.jpg"
    )
    result = rule.evaluate(media, {})
    assert result.score == 1.00


def test_sent_directory_segment_sets_whatsapp_sent_label() -> None:
    media = _media(
        "IMG-20260730-WA0001.jpg", relative_path="WhatsApp Images/Sent/IMG-20260730-WA0001.jpg"
    )
    result = rule.evaluate(media, {})
    assert result.label == "whatsapp_sent"


def test_no_sent_directory_defaults_to_whatsapp_received() -> None:
    media = _media(
        "IMG-20260730-WA0001.jpg", relative_path="WhatsApp Images/IMG-20260730-WA0001.jpg"
    )
    result = rule.evaluate(media, {})
    assert result.label == "whatsapp_received"


def test_readme_12_4_absent_metadata_alone_does_not_classify() -> None:
    media = _media("random_photo.jpg")
    result = rule.evaluate(media, {})
    assert result.score == 0.0
    assert result.label == "unknown"


def test_no_signals_at_all_scores_zero() -> None:
    media = _media("random_photo.jpg")
    result = rule.evaluate(media, {"Make": "Canon"})
    assert result.score == 0.0
