"""Integration tests: scan a folder, then detect media types over its rows — see
specs/2026-08-07-phase-5-media-type-detection/plan.md and validation.md.
"""

from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models.media_file import MediaFile
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.scanner import scan_folder

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _copy_fixtures(root: Path) -> None:
    for name in (
        "iphone_jpeg_gps.jpg",
        "iphone_heic.heic",
        "jpeg_no_exif.jpg",
        "Screenshot_20260730-152000.png",
        "IMG-20260730-WA0001.jpg",
        "sample_video.mp4",
        "misnamed_video_as_jpg.jpg",
    ):
        shutil.copy(FIXTURES_DIR / name, root / name)


def test_detect_media_types_for_scan_persists_results(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _copy_fixtures(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None

        summary = detect_media_types_for_scan(session, scan.id)

        media_repo = MediaFileRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

    assert rows["misnamed_video_as_jpg.jpg"].media_kind == "video"
    assert rows["misnamed_video_as_jpg.jpg"].extension_mismatch is True
    assert rows["sample_video.mp4"].media_kind == "video"
    assert rows["sample_video.mp4"].extension_mismatch is False
    assert rows["iphone_jpeg_gps.jpg"].media_kind == "image"
    assert rows["iphone_heic.heic"].media_kind == "image"

    assert summary.images == 5
    assert summary.videos == 2
    assert summary.mismatches == 1
    assert summary.read_errors == 0


def test_detect_media_types_for_scan_records_read_errors_without_aborting(
    engine: Engine, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "ok.jpg").write_bytes(b"\xff\xd8\xff\xe0fake jpeg bytes")
    doomed = root / "vanishes.jpg"
    doomed.write_bytes(b"\xff\xd8\xff\xe0will be deleted")

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        doomed.unlink()

        summary = detect_media_types_for_scan(session, scan.id)

        media_repo = MediaFileRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

    assert rows["ok.jpg"].media_kind == "image"
    assert rows["vanishes.jpg"].error_code == "SIGNATURE_READ_ERROR"
    assert rows["vanishes.jpg"].media_kind is None
    assert summary.read_errors == 1


def test_detect_media_types_commits_and_reports_once_per_batch(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    for index in range(5):
        (root / f"photo-{index}.jpg").write_bytes(b"\xff\xd8\xff\xe0fake jpeg")

    saved_batch_sizes: list[int] = []
    original_save_many = MediaFileRepository.save_many

    def _record_save_many(repository: MediaFileRepository, rows: Sequence[MediaFile]) -> None:
        saved_batch_sizes.append(len(rows))
        original_save_many(repository, rows)

    progress: list[int] = []
    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        saved_batch_sizes.clear()
        monkeypatch.setattr(MediaFileRepository, "save_many", _record_save_many)

        detect_media_types_for_scan(
            session,
            scan.id,
            batch_size=2,
            on_progress=progress.append,
        )

    assert saved_batch_sizes == [2, 2, 1]
    assert progress == [2, 4, 5]
