"""Integration tests for the scanner service — see
specs/2026-08-07-phase-4-scanner/plan.md and validation.md.
"""

from __future__ import annotations

import os
import unicodedata
from pathlib import Path

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.core.paths import to_nfc
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.services.scanner import InvalidSourceRootError, ScanProgress, scan_folder

NFD_NAME = unicodedata.normalize("NFD", "café.jpg")
NFC_NAME = unicodedata.normalize("NFC", "café.jpg")


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _build_tree(root: Path) -> None:
    """A nested tree exercising every ignore rule plus an NFD/NFC pair.

    root/
      top.jpg
      nested/
        inner.jpg
        Thumbs.db                 (ignored file)
        ._sidecar.jpg             (ignored AppleDouble file)
        <NFD café.jpg>            (NFD-named, must persist as NFC)
        .Spotlight-V100/          (ignored dir, pruned entirely)
          should-not-be-seen.jpg
    """
    (root / "top.jpg").write_bytes(b"top")
    nested = root / "nested"
    nested.mkdir()
    (nested / "inner.jpg").write_bytes(b"inner12")
    (nested / "Thumbs.db").write_bytes(b"junk")
    (nested / "._sidecar.jpg").write_bytes(b"sidecar")
    (nested / NFD_NAME).write_bytes(b"nfd")
    spotlight = nested / ".Spotlight-V100"
    spotlight.mkdir()
    (spotlight / "should-not-be-seen.jpg").write_bytes(b"pruned")


def test_scan_folder_persists_expected_files_and_skips_ignored(
    engine: Engine, tmp_path: Path
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    _build_tree(root)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        media_repo = MediaFileRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

    assert set(rows) == {
        "top.jpg",
        "nested/inner.jpg",
        f"nested/{to_nfc(NFD_NAME)}",
    }
    assert rows[f"nested/{to_nfc(NFD_NAME)}"].relative_path == f"nested/{NFC_NAME}"
    assert rows["top.jpg"].processing_status == "pending"
    assert rows["top.jpg"].size_bytes == len(b"top")
    assert scan.status == "completed"
    assert scan.total_files == 3
    assert scan.total_bytes == len(b"top") + len(b"inner12") + len(b"nfd")


def test_scan_folder_records_access_error_without_aborting(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "ok.jpg").write_bytes(b"ok")
    unreadable = root / "unreadable.jpg"
    unreadable.write_bytes(b"blocked")

    original_stat = Path.stat

    def fake_stat(self: Path, *, follow_symlinks: bool = True) -> os.stat_result:
        # `follow_symlinks=False` is the `lstat()` used internally by `is_symlink()`
        # during the walk; only the real `stat()` call (checking readability) fails.
        if self == unreadable and follow_symlinks:
            raise OSError("permission denied")
        return original_stat(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", fake_stat)

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        media_repo = MediaFileRepository(session)
        rows = {mf.relative_path: mf for mf in media_repo.list_by_scan(scan.id)}

    assert scan.status == "completed"
    assert rows["unreadable.jpg"].processing_status == "error"
    assert rows["unreadable.jpg"].error_code == "ACCESS_ERROR"
    assert rows["ok.jpg"].processing_status == "pending"
    assert scan.total_files == 2
    assert scan.total_bytes == len(b"ok")


def test_scan_folder_does_not_follow_symlinks(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.jpg").write_bytes(b"outside")

    real_file = root / "real.jpg"
    real_file.write_bytes(b"real")

    try:
        (root / "link_to_outside").symlink_to(outside, target_is_directory=True)
        (root / "link_file.jpg").symlink_to(real_file)
    except OSError as error:
        pytest.skip(f"symlink creation not permitted in this environment: {error}")

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True)
        assert scan.id is not None
        media_repo = MediaFileRepository(session)
        files = {mf.relative_path for mf in media_repo.list_by_scan(scan.id)}

    assert files == {"real.jpg"}


def test_scan_folder_non_recursive_only_scans_top_level(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "top.jpg").write_bytes(b"top")
    nested = root / "nested"
    nested.mkdir()
    (nested / "inner.jpg").write_bytes(b"inner")

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=False)
        assert scan.id is not None
        media_repo = MediaFileRepository(session)
        files = {mf.relative_path for mf in media_repo.list_by_scan(scan.id)}

    assert files == {"top.jpg"}
    assert scan.recursive is False


def test_scan_folder_invokes_progress_callback(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    for index in range(5):
        (root / f"file{index}.jpg").write_bytes(b"x")

    progress_events: list[ScanProgress] = []

    with get_session(engine) as session:
        scan_folder(
            session,
            root,
            recursive=True,
            batch_size=2,
            on_progress=progress_events.append,
        )

    assert len(progress_events) >= 2
    assert progress_events[-1].processed_files == 5


def test_scan_folder_rejects_missing_source_root(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session, pytest.raises(InvalidSourceRootError):
        scan_folder(session, tmp_path / "missing", recursive=True)


def test_scan_folder_skips_excluded_dirs(engine: Engine, tmp_path: Path) -> None:
    root = tmp_path / "source"
    root.mkdir()
    (root / "keep.jpg").write_bytes(b"keep")
    excluded = root / "reports"
    excluded.mkdir()
    (excluded / "report.jpg").write_bytes(b"skip")

    with get_session(engine) as session:
        scan = scan_folder(session, root, recursive=True, exclude_dirs=[excluded])
        assert scan.id is not None
        media_repo = MediaFileRepository(session)
        files = {mf.relative_path for mf in media_repo.list_by_scan(scan.id)}

    assert files == {"keep.jpg"}
