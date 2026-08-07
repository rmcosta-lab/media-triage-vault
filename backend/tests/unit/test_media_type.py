"""Unit tests for media type detection — see
specs/2026-08-07-phase-5-media-type-detection/plan.md and validation.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.media_type import _sniff_signature, detect_media_type

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (b"\xff\xd8\xff\xe0" + b"\x00" * 10, "image"),  # JPEG
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image"),  # PNG
        (b"GIF89a" + b"\x00" * 10, "image"),  # GIF
        (b"BM" + b"\x00" * 10, "image"),  # BMP
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image"),  # WEBP
        (b"RIFF\x00\x00\x00\x00AVI LIST", "video"),  # AVI
        (b"II*\x00" + b"\x00" * 10, "image"),  # TIFF little-endian / TIFF-based RAW
        (b"MM\x00*" + b"\x00" * 10, "image"),  # TIFF big-endian
        (b"FUJIFILMCCD-RAW" + b"\x00" * 10, "image"),  # Fujifilm RAF
        (b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00", "image"),  # HEIC ftyp
        (b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00", "video"),  # MP4 ftyp
        (b"\x1a\x45\xdf\xa3" + b"\x00" * 10, "video"),  # EBML (MKV/WEBM)
        (b"not a media file at all", None),
    ],
)
def test_sniff_signature(header: bytes, expected: str | None) -> None:
    assert _sniff_signature(header) == expected


@pytest.mark.parametrize(
    ("fixture_name", "expected_kind"),
    [
        ("iphone_jpeg_gps.jpg", "image"),
        ("iphone_heic.heic", "image"),
        ("jpeg_no_exif.jpg", "image"),
        ("Screenshot_20260730-152000.png", "image"),
        ("IMG-20260730-WA0001.jpg", "image"),
        ("sample_video.mp4", "video"),
    ],
)
def test_detect_media_type_matches_content_for_correctly_named_fixtures(
    fixture_name: str, expected_kind: str
) -> None:
    path = FIXTURES_DIR / fixture_name
    detection = detect_media_type(path, path.suffix)

    assert detection.media_kind == expected_kind
    assert detection.extension_mismatch is False


def test_detect_media_type_flags_misnamed_video_fixture() -> None:
    path = FIXTURES_DIR / "misnamed_video_as_jpg.jpg"
    detection = detect_media_type(path, path.suffix)

    assert detection.media_kind == "video"
    assert detection.extension_mismatch is True


def test_detect_media_type_unknown_extension_and_signature_is_unsupported(tmp_path: Path) -> None:
    path = tmp_path / "mystery.xyz"
    path.write_bytes(b"not a recognizable format")

    detection = detect_media_type(path, path.suffix)

    assert detection.media_kind == "unsupported"
    assert detection.extension_mismatch is False


def test_detect_media_type_falls_back_to_extension_when_signature_unrecognized(
    tmp_path: Path,
) -> None:
    path = tmp_path / "truncated.jpg"
    path.write_bytes(b"not really a jpeg")

    detection = detect_media_type(path, path.suffix)

    assert detection.media_kind == "image"
    assert detection.mime_type == "image/jpeg"
    assert detection.extension_mismatch is False
