"""Unit tests for backend.app.services.metadata — see
specs/2026-08-07-phase-6-batch-metadata-extraction/plan.md and validation.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from backend.app.core.tools import run_tool
from backend.app.services.metadata import (
    EXIFTOOL_FIELDS,
    _build_media_metadata,
    _parse_exiftool_datetime,
    _resolve_capture_datetime,
    _run_exiftool_batch,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def test_parse_exiftool_datetime_valid() -> None:
    assert _parse_exiftool_datetime("2026:07:30 15:20:00") is not None


def test_parse_exiftool_datetime_malformed_returns_none() -> None:
    assert _parse_exiftool_datetime("not a date") is None
    assert _parse_exiftool_datetime(None) is None
    assert _parse_exiftool_datetime(1234) is None


def test_resolve_capture_datetime_priority_order() -> None:
    tags = {
        "CreateDate": "2026:01:01 00:00:00",
        "DateTimeOriginal": "2026:07:30 15:20:00",
        "MediaCreateDate": "2025:01:01 00:00:00",
    }
    resolved = _resolve_capture_datetime(tags)
    assert resolved is not None
    assert resolved.year == 2026 and resolved.month == 7 and resolved.day == 30


def test_resolve_capture_datetime_falls_back_when_first_choice_missing() -> None:
    tags = {"MediaCreateDate": "2025:03:04 05:06:07"}
    resolved = _resolve_capture_datetime(tags)
    assert resolved is not None
    assert resolved.year == 2025


def test_resolve_capture_datetime_none_when_nothing_parses() -> None:
    assert _resolve_capture_datetime({}) is None


def test_build_media_metadata_full_tag_dict() -> None:
    tags = {
        "Make": "Apple",
        "Model": "iPhone 14 Pro",
        "DateTimeOriginal": "2026:07:30 15:20:00",
        "GPSLatitude": 35.6762,
        "GPSLongitude": 139.6503,
        "GPSPosition": "35.6762 139.6503",
        "Rotation": 90,
        "ColorSpace": "sRGB",
        "Unrelated": "should not leak into raw_json",
    }
    metadata = _build_media_metadata(media_file_id=1, tags=tags)
    assert metadata.media_file_id == 1
    assert metadata.make == "Apple"
    assert metadata.model == "iPhone 14 Pro"
    assert metadata.gps_latitude == 35.6762
    assert metadata.gps_longitude == 139.6503
    assert metadata.rotation == 90
    assert metadata.color_space == "sRGB"
    assert metadata.capture_datetime is not None

    raw = json.loads(metadata.raw_json or "{}")
    assert "Unrelated" not in raw
    assert set(raw).issubset(set(EXIFTOOL_FIELDS))


def test_build_media_metadata_partial_tag_dict_leaves_rest_none() -> None:
    metadata = _build_media_metadata(media_file_id=2, tags={"Make": "Canon"})
    assert metadata.make == "Canon"
    assert metadata.model is None
    assert metadata.gps_latitude is None
    assert metadata.capture_datetime is None


def test_run_exiftool_batch_uses_one_process_for_multiple_files() -> None:
    fixtures = [
        FIXTURES_DIR / "iphone_jpeg_gps.jpg",
        FIXTURES_DIR / "jpeg_no_exif.jpg",
        FIXTURES_DIR / "sample_video.mp4",
    ]
    with patch("backend.app.services.metadata.run_tool", wraps=run_tool) as mocked:
        results = _run_exiftool_batch(fixtures)

    assert mocked.call_count == 1
    assert len(results) == len(fixtures)
    assert results[0]["Make"] == "Apple"
