"""Unit tests for backend.app.services.thumbnails — see
specs/2026-08-07-phase-13-thumbnails-static-reports/plan.md and validation.md.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
import rawpy
from PIL import Image
from rawpy._rawpy import ThumbFormat

from backend.app.models.media_file import MediaFile
from backend.app.services import thumbnails as thumbnails_module
from backend.app.services.thumbnails import generate_thumbnail

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


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


@pytest.mark.parametrize(
    "file_name,extension",
    [
        ("iphone_jpeg_gps.jpg", ".jpg"),
        ("iphone_heic.heic", ".heic"),
        ("IMG-20260730-WA0001.jpg", ".jpg"),
        ("Screenshot_20260730-152000.png", ".png"),
        ("jpeg_no_exif.jpg", ".jpg"),
    ],
)
def test_generate_thumbnail_for_standard_and_heic_images(
    tmp_path: Path, file_name: str, extension: str
) -> None:
    media = _media(
        absolute_path=str(FIXTURES_DIR / file_name),
        relative_path=file_name,
        file_name=file_name,
        extension=extension,
        media_kind="image",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is True
    assert destination.is_file()
    with Image.open(destination) as image:
        assert max(image.size) <= thumbnails_module.THUMBNAIL_MAX_DIMENSION


def test_generate_thumbnail_for_video(tmp_path: Path) -> None:
    media = _media(
        absolute_path=str(FIXTURES_DIR / "sample_video.mp4"),
        relative_path="sample_video.mp4",
        file_name="sample_video.mp4",
        extension=".mp4",
        media_kind="video",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is True
    assert destination.is_file()


def test_generate_thumbnail_for_corrupt_video_fails_without_raising(tmp_path: Path) -> None:
    media = _media(
        absolute_path=str(FIXTURES_DIR / "corrupt_video.mp4"),
        relative_path="corrupt_video.mp4",
        file_name="corrupt_video.mp4",
        extension=".mp4",
        media_kind="video",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is False
    assert result.error_code == "THUMBNAIL_VIDEO_ERROR"
    assert not destination.exists()


def test_generate_thumbnail_dispatches_misnamed_video_by_media_kind(tmp_path: Path) -> None:
    """A `.jpg`-named file whose `media_kind` is `video` (Phase 5's mismatch case)
    must go through the video path, not the image decoder."""
    media = _media(
        absolute_path=str(FIXTURES_DIR / "misnamed_video_as_jpg.jpg"),
        relative_path="misnamed_video_as_jpg.jpg",
        file_name="misnamed_video_as_jpg.jpg",
        extension=".jpg",
        media_kind="video",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is True
    assert destination.is_file()


def test_generate_thumbnail_unsupported_media_kind(tmp_path: Path) -> None:
    media = _media(media_kind="unsupported", extension=".xyz")
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is False
    assert result.error_code == "UNSUPPORTED_MEDIA_KIND"


class _FakeThumb:
    def __init__(self, format_: Any, data: Any) -> None:
        self.format = format_
        self.data = data


class _FakeRawReaderWithThumb:
    def __enter__(self) -> _FakeRawReaderWithThumb:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def extract_thumb(self) -> _FakeThumb:
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), (10, 20, 30)).save(buffer, format="JPEG")
        return _FakeThumb(ThumbFormat.JPEG, buffer.getvalue())


def test_generate_thumbnail_raw_success_via_embedded_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(rawpy, "imread", lambda path: _FakeRawReaderWithThumb())
    raw_path = tmp_path / "photo.dng"
    raw_path.write_bytes(b"not real raw data")
    media = _media(
        absolute_path=str(raw_path),
        relative_path="photo.dng",
        file_name="photo.dng",
        extension=".dng",
        media_kind="image",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is True
    assert destination.is_file()


def test_generate_thumbnail_raw_failure_on_invalid_file(tmp_path: Path) -> None:
    """No real DNG fixture exists (Phase 9 hit the same gap for IPhoneRawRule);
    a file with arbitrary bytes still proves the LibRawError -> failure path."""
    raw_path = tmp_path / "invalid.dng"
    raw_path.write_bytes(b"not a real raw file" * 10)
    media = _media(
        absolute_path=str(raw_path),
        relative_path="invalid.dng",
        file_name="invalid.dng",
        extension=".dng",
        media_kind="image",
    )
    destination = tmp_path / "thumb.jpg"

    result = generate_thumbnail(media, destination)

    assert result.success is False
    assert result.error_code == "THUMBNAIL_RAW_DECODE_ERROR"
