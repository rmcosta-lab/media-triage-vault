"""Unit tests for the move report — README §19.3, roadmap Phase 16."""

from __future__ import annotations

import csv
import json
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
from backend.app.services.move_report import generate_move_report


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


def _make_source_file(tmp_path: Path, relative: str) -> Path:
    path = tmp_path / "source" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"payload")
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


def _make_operation(
    session: Session,
    plan: MovePlan,
    scan_id: int,
    media_file: MediaFile,
    source: Path,
    *,
    status: str,
    error_code: str | None = None,
    destination_size: int | None = None,
) -> MoveOperation:
    assert media_file.id is not None
    assert plan.id is not None
    return MoveOperationRepository(session).create(
        MoveOperation(
            move_plan_id=plan.id,
            scan_id=scan_id,
            media_file_id=media_file.id,
            source_path=str(source),
            planned_destination_path=str(source.parent / "dest" / source.name),
            source_size=source.stat().st_size,
            destination_size=destination_size,
            status=status,
            error_code=error_code,
            finished_at=datetime.now(UTC) if status in ("completed", "failed") else None,
        )
    )


def test_generate_move_report_writes_json_and_csv(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        plan = MovePlanRepository(session).create(
            MovePlan(scan_id=scan_id, status="generated", validation_mode="standard")
        )
        assert plan.id is not None

        completed_source = _make_source_file(tmp_path, "ok.jpg")
        failed_source = _make_source_file(tmp_path, "bad.jpg")
        blocked_source = _make_source_file(tmp_path, "blocked.jpg")
        planned_source = _make_source_file(tmp_path, "later.jpg")

        media_ok = _make_media_file(session, scan_id, completed_source)
        media_bad = _make_media_file(session, scan_id, failed_source)
        media_blocked = _make_media_file(session, scan_id, blocked_source)
        media_planned = _make_media_file(session, scan_id, planned_source)

        _make_operation(
            session,
            plan,
            scan_id,
            media_ok,
            completed_source,
            status="completed",
            destination_size=completed_source.stat().st_size,
        )
        _make_operation(
            session,
            plan,
            scan_id,
            media_bad,
            failed_source,
            status="failed",
            error_code="HASH_MISMATCH",
        )
        _make_operation(session, plan, scan_id, media_blocked, blocked_source, status="blocked")
        _make_operation(session, plan, scan_id, media_planned, planned_source, status="planned")

        output_dir = tmp_path / "report"
        summary = generate_move_report(session, plan.id, output_dir, 12.5)

        assert summary.total_operations == 4
        assert summary.total_completed == 1
        assert summary.total_failed == 1
        assert summary.total_blocked == 1
        assert summary.total_planned == 1
        assert summary.total_bytes_moved == 7
        assert summary.elapsed_seconds == 12.5

        report_json = json.loads((output_dir / "move_report.json").read_text(encoding="utf-8"))
        assert report_json["move_plan_id"] == plan.id
        assert report_json["totals"]["operations"] == 4
        assert report_json["totals"]["completed"] == 1
        assert report_json["by_error_code"] == {"HASH_MISMATCH": 1}
        assert len(report_json["operations"]) == 4

        with open(output_dir / "move_report.csv", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 4
        statuses = {row["status"] for row in rows}
        assert statuses == {"completed", "failed", "blocked", "planned"}


def test_generate_move_report_missing_plan_raises(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session, pytest.raises(ValueError, match="No move plan found"):
        generate_move_report(session, 999, tmp_path / "report", 0.0)
