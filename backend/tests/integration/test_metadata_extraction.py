"""Integration tests: scan -> detect -> extract metadata over fixture rows — see
specs/2026-08-07-phase-6-batch-metadata-extraction/plan.md and validation.md.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.core.tools import run_tool
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.services import metadata as metadata_module
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
from backend.app.services.scanner import scan_folder

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

ALL_FIXTURES = (
    "iphone_jpeg_gps.jpg",
    "iphone_heic.heic",
    "jpeg_no_exif.jpg",
    "Screenshot_20260730-152000.png",
    "IMG-20260730-WA0001.jpg",
    "sample_video.mp4",
    "misnamed_video_as_jpg.jpg",
    "corrupt_video.mp4",
)


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _copy_fixtures(root: Path) -> None:
    for name in ALL_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, root / name)


def test_extract_metadata_for_scan_persists_normalized_fields(
    engine: Engine, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        detect_media_types_for_scan(session, scan.id)

        summary = extract_metadata_for_scan(session, scan.id)

        media_repo = MediaFileRepository(session)
        metadata_repo = MediaMetadataRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

        iphone_row = rows["iphone_jpeg_gps.jpg"]
        assert iphone_row.id is not None
        iphone_metadata = metadata_repo.get_by_media_file_id(iphone_row.id)
        assert iphone_metadata is not None
        assert iphone_metadata.make == "Apple"
        assert iphone_metadata.model == "iPhone 14 Pro"
        assert iphone_metadata.gps_latitude is not None
        assert iphone_metadata.gps_longitude is not None
        assert iphone_metadata.capture_datetime is not None

        video_row = rows["sample_video.mp4"]
        assert video_row.width == 64
        assert video_row.height == 64
        assert video_row.duration_seconds is not None
        assert video_row.processing_status == "pending"

        corrupt_row = rows["corrupt_video.mp4"]
        assert corrupt_row.media_kind == "video"
        assert corrupt_row.processing_status == "error"
        assert corrupt_row.error_code == "VIDEO_UNREADABLE"

    assert summary.video_unreadable == 1
    assert summary.video_ok == 2
    assert summary.extracted >= 6


def test_extract_metadata_for_scan_uses_single_batch_for_all_pending_files(
    engine: Engine, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        detect_media_types_for_scan(session, scan.id)

        with patch("backend.app.services.metadata.run_tool", wraps=run_tool) as mocked_run_tool:
            extract_metadata_for_scan(session, scan.id)

    exiftool_calls = [call for call in mocked_run_tool.call_args_list if call.args[0] == "exiftool"]
    assert len(exiftool_calls) == 1


def test_metadata_batch_rolls_back_when_video_validation_crashes(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", root / "photo.jpg")
    shutil.copy(FIXTURES_DIR / "sample_video.mp4", root / "video.mp4")

    def _crash(_row: object) -> bool:
        raise RuntimeError("ffprobe crashed")

    progress: list[int] = []
    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        scan_id = scan.id
        detect_media_types_for_scan(session, scan_id)
        monkeypatch.setattr(metadata_module, "_validate_video", _crash)

        with pytest.raises(RuntimeError, match="ffprobe crashed"):
            extract_metadata_for_scan(session, scan_id, on_progress=progress.append)

    assert progress == []
    with get_session(engine) as session:
        media_files = MediaFileRepository(session).list_by_scan(scan_id)
        media_file_ids = [row.id for row in media_files if row.id is not None]
        assert MediaMetadataRepository(session).list_by_media_file_ids(media_file_ids) == []
        for row in media_files:
            assert row.file_type is None
            assert row.width is None
            assert row.height is None
            assert row.duration_seconds is None
            assert row.error_code is None
