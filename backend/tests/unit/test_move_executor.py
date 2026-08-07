"""Unit tests for the transactional move executor — README §17/§18, roadmap Phase 15."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.core.paths import absolute_nfc
from backend.app.models.media_file import MediaFile
from backend.app.models.move_plan import MoveOperation, MovePlan
from backend.app.models.scan import Scan
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services import move_executor as move_executor_module
from backend.app.services.move_executor import execute_move_plan


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _make_scan(session: Session) -> int:
    scan = ScanRepository(session).create(
        Scan(source_root="D:/Fotos", recursive=True, status="pending")
    )
    assert scan.id is not None
    return scan.id


def _make_source_file(tmp_path: Path, relative: str, content: bytes = b"payload") -> Path:
    path = tmp_path / "source" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _make_media_file(session: Session, scan_id: int, source_path: Path) -> MediaFile:
    stat_result = source_path.stat()
    return MediaFileRepository(session).create(
        MediaFile(
            scan_id=scan_id,
            absolute_path=absolute_nfc(source_path),
            relative_path=source_path.name,
            file_name=source_path.name,
            extension=source_path.suffix,
            size_bytes=stat_result.st_size,
            modified_at=datetime.fromtimestamp(stat_result.st_mtime, tz=UTC),
            processing_status="processed",
        )
    )


def _make_move_plan(
    session: Session, scan_id: int, *, validation_mode: str = "standard"
) -> MovePlan:
    plan = MovePlanRepository(session).create(
        MovePlan(scan_id=scan_id, status="generated", validation_mode=validation_mode)
    )
    assert plan.id is not None
    return plan


def _make_operation(
    session: Session,
    plan: MovePlan,
    scan_id: int,
    media_file: MediaFile,
    source: Path,
    destination: Path,
    *,
    status: str = "planned",
) -> MoveOperation:
    assert media_file.id is not None
    assert plan.id is not None
    return MoveOperationRepository(session).create(
        MoveOperation(
            move_plan_id=plan.id,
            scan_id=scan_id,
            media_file_id=media_file.id,
            source_path=str(source),
            planned_destination_path=str(destination),
            source_size=source.stat().st_size,
            status=status,
        )
    )


def test_same_volume_rename_completes(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "photo.jpg"
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_completed == 1
        assert summary.total_failed == 0
        assert destination.exists()
        assert not source.exists()

        session.refresh(operation)
        assert operation.status == "completed"
        assert operation.actual_destination_path == str(destination)
        assert operation.destination_size == destination.stat().st_size
        assert operation.source_hash is None
        assert operation.destination_hash is None


def test_strict_mode_hashes_same_volume_rename(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg", content=b"strict-content")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "photo.jpg"
        plan = _make_move_plan(session, scan_id, validation_mode="strict")
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        session.refresh(operation)
        assert operation.status == "completed"
        assert operation.source_hash is not None
        assert operation.source_hash == operation.destination_hash


def test_cross_volume_copy_completes(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(move_executor_module, "is_same_volume", lambda source, dest: False)

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "video.mp4", content=b"cross-volume-content")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "video.mp4"
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_completed == 1
        assert destination.read_bytes() == b"cross-volume-content"
        assert not source.exists()
        assert list(destination.parent.glob("*.partial-*")) == []

        session.refresh(operation)
        assert operation.status == "completed"
        assert operation.source_hash is not None
        assert operation.source_hash == operation.destination_hash


def test_mid_copy_failure_leaves_no_partial_and_source_untouched(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(move_executor_module, "is_same_volume", lambda source, dest: False)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copyfileobj", _raise)

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "video.mp4")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "video.mp4"
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_failed == 1
        assert summary.by_error_code == {"COPY_FAILED": 1}
        assert source.exists()
        assert not destination.exists()
        assert list(tmp_path.rglob("*.partial-*")) == []

        session.refresh(operation)
        assert operation.status == "failed"
        assert operation.error_code == "COPY_FAILED"


def test_hash_mismatch_fails_and_cleans_up_partial(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(move_executor_module, "is_same_volume", lambda source, dest: False)

    def _fake_hash(path: Path, *_args: object, **_kwargs: object) -> str:
        return "partial-digest" if ".partial-" in str(path) else "source-digest"

    monkeypatch.setattr(move_executor_module, "sha256_file", _fake_hash)

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "video.mp4")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "video.mp4"
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_failed == 1
        assert summary.by_error_code == {"HASH_MISMATCH": 1}
        assert source.exists()
        assert not destination.exists()
        assert list(tmp_path.rglob("*.partial-*")) == []

        session.refresh(operation)
        assert operation.status == "failed"
        assert operation.error_code == "HASH_MISMATCH"


def test_destination_exists_at_execution_time_fails(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "photo.jpg"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"already here")
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(session, plan, scan_id, media_file, source, destination)

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_failed == 1
        assert source.exists()
        assert destination.read_bytes() == b"already here"

        session.refresh(operation)
        assert operation.status == "failed"
        assert operation.error_code == "DESTINATION_EXISTS"


def test_idempotent_rerun_of_completed_plan_is_a_no_op(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "photo.jpg"
        plan = _make_move_plan(session, scan_id)
        _make_operation(session, plan, scan_id, media_file, source, destination)

        first = execute_move_plan(session, plan.id)  # type: ignore[arg-type]
        assert first.total_completed == 1
        mtime_after_first = destination.stat().st_mtime

        second = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert second.total_completed == 1
        assert second.total_failed == 0
        assert destination.stat().st_mtime == mtime_after_first


def test_resume_after_crash_with_leftover_partial(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(move_executor_module, "is_same_volume", lambda source, dest: False)

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "video.mp4", content=b"fresh-content")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "video.mp4"
        destination.parent.mkdir(parents=True)
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(
            session, plan, scan_id, media_file, source, destination, status="copying"
        )
        assert operation.id is not None
        stray_partial = destination.with_name(f"{destination.name}.partial-{operation.id}")
        stray_partial.write_bytes(b"stale-garbage-from-a-crashed-run")

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_completed == 1
        assert destination.read_bytes() == b"fresh-content"
        assert not stray_partial.exists()
        assert not source.exists()

        session.refresh(operation)
        assert operation.status == "completed"


def test_resume_when_move_already_finished_before_crash(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "video.mp4", content=b"already-moved")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "video.mp4"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"already-moved")
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(
            session, plan, scan_id, media_file, source, destination, status="renaming"
        )
        operation.actual_destination_path = str(destination)
        MoveOperationRepository(session).update(operation)
        mtime_before = destination.stat().st_mtime

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_completed == 1
        assert destination.stat().st_mtime == mtime_before
        assert list(tmp_path.rglob("*.partial-*")) == []

        session.refresh(operation)
        assert operation.status == "completed"


def test_blocked_operation_is_left_untouched(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        destination = tmp_path / "dest" / "photo.jpg"
        plan = _make_move_plan(session, scan_id)
        operation = _make_operation(
            session, plan, scan_id, media_file, source, destination, status="blocked"
        )

        summary = execute_move_plan(session, plan.id)  # type: ignore[arg-type]

        assert summary.total_completed == 0
        assert summary.total_failed == 0
        assert source.exists()
        assert not destination.exists()

        session.refresh(operation)
        assert operation.status == "blocked"
