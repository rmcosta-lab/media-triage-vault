"""Unit tests for the move-plan (dry-run) service — README §16 Etapa 5, roadmap Phase 14."""

from __future__ import annotations

from collections import namedtuple
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.core.paths import absolute_nfc
from backend.app.models.classification import Classification
from backend.app.models.destination_rule import DestinationRule
from backend.app.models.media_file import MediaFile
from backend.app.models.move_plan import MoveOperation
from backend.app.models.scan import Scan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.destination_rule_repository import DestinationRuleRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.move_plan_repository import MovePlanRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services import move_plan as move_plan_module
from backend.app.services.move_plan import generate_move_plan

_DiskUsage = namedtuple("_DiskUsage", ["total", "used", "free"])


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


def _make_source_file(tmp_path: Path, relative: str, content: bytes = b"x") -> Path:
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


def _make_classification(
    session: Session,
    media_file_id: int,
    routing_group: str,
    *,
    country_name: str | None = None,
    country_code: str | None = None,
) -> Classification:
    return ClassificationRepository(session).create(
        Classification(
            media_file_id=media_file_id,
            media_kind="image",
            source_origin="other",
            image_format="standard",
            automatic_routing_group=routing_group,
            effective_routing_group=routing_group,
            confidence=0.9,
            requires_review=False,
            reasons_json="[]",
            country_name=country_name,
            country_code=country_code,
        )
    )


def _make_rule(
    session: Session,
    scan_id: int,
    routing_group: str,
    destination_root: str,
    *,
    country_subfolder_enabled: bool = False,
) -> None:
    DestinationRuleRepository(session).create(
        DestinationRule(
            scan_id=scan_id,
            routing_group=routing_group,
            destination_root=destination_root,
            country_subfolder_enabled=country_subfolder_enabled,
            enabled=True,
        )
    )


def _operation_for(session: Session, scan_id: int, media_file_id: int) -> MoveOperation:
    move_plan = MovePlanRepository(session).get_latest_for_scan(scan_id)
    assert move_plan is not None
    assert move_plan.id is not None
    operations = MoveOperationRepository(session).list_by_plan(move_plan.id)
    return next(op for op in operations if op.media_file_id == media_file_id)


def test_happy_path_one_file_one_mapped_group(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        dest_root = tmp_path / "dest"
        _make_rule(session, scan_id, "other", str(dest_root))

        summary = generate_move_plan(session, scan_id)

        assert summary.total_planned == 1
        assert summary.total_blocked == 0
        assert summary.total_bytes_planned == source.stat().st_size

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "planned"
        assert operation.planned_destination_path == absolute_nfc(dest_root / "other" / "photo.jpg")
        assert not dest_root.exists()


def test_case_only_collision_is_blocked(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "foto.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")

        dest_root = tmp_path / "dest"
        (dest_root / "other").mkdir(parents=True)
        (dest_root / "other" / "Foto.jpg").write_bytes(b"already here")
        _make_rule(session, scan_id, "other", str(dest_root))

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "NAME_COLLISION"


def test_over_length_path_is_blocked(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")

        dest_root = str(tmp_path) + "/" + ("a" * 250)
        _make_rule(session, scan_id, "other", dest_root)

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "PATH_TOO_LONG"


def test_duplicate_in_plan_is_blocked_on_second_file(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source_a = _make_source_file(tmp_path, "a/dup.jpg")
        source_b = _make_source_file(tmp_path, "b/dup.jpg")
        media_a = _make_media_file(session, scan_id, source_a)
        media_b = _make_media_file(session, scan_id, source_b)
        assert media_a.id is not None
        assert media_b.id is not None
        _make_classification(session, media_a.id, "other")
        _make_classification(session, media_b.id, "other")

        dest_root = tmp_path / "dest"
        _make_rule(session, scan_id, "other", str(dest_root))

        generate_move_plan(session, scan_id)

        op_a = _operation_for(session, scan_id, media_a.id)
        op_b = _operation_for(session, scan_id, media_b.id)
        statuses = {op_a.status, op_b.status}
        assert statuses == {"planned", "blocked"}
        blocked = op_a if op_a.status == "blocked" else op_b
        assert blocked.error_code == "DUPLICATE_IN_PLAN"


def test_source_missing_is_blocked(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        _make_rule(session, scan_id, "other", str(tmp_path / "dest"))

        source.unlink()

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "SOURCE_MISSING"


def test_source_changed_since_scan_is_blocked(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        _make_rule(session, scan_id, "other", str(tmp_path / "dest"))

        source.write_bytes(b"a completely different, longer payload")

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "SOURCE_CHANGED"


def test_source_equals_destination_is_blocked(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "other/photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        _make_rule(session, scan_id, "other", str(source.parent.parent))

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "SOURCE_EQUALS_DESTINATION"


def test_source_locked_is_blocked(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(move_plan_module, "_is_locked", lambda path: True)

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        _make_rule(session, scan_id, "other", str(tmp_path / "dest"))

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "SOURCE_LOCKED"


def test_insufficient_disk_space_is_blocked(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("shutil.disk_usage", lambda path: _DiskUsage(total=0, used=0, free=0))

    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        _make_rule(session, scan_id, "other", str(tmp_path / "dest"))

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.status == "blocked"
        assert operation.error_code == "INSUFFICIENT_DISK_SPACE"


def test_country_subfolder_enabled_adds_segment(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "iphone_photo", country_name="Japan")
        dest_root = tmp_path / "dest"
        _make_rule(session, scan_id, "iphone_photo", str(dest_root), country_subfolder_enabled=True)

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.planned_destination_path == absolute_nfc(
            dest_root / "iphone_photo" / "Japan" / "photo.jpg"
        )


def test_country_subfolder_disabled_is_flat(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "iphone_photo", country_name="Japan")
        dest_root = tmp_path / "dest"
        _make_rule(
            session, scan_id, "iphone_photo", str(dest_root), country_subfolder_enabled=False
        )

        generate_move_plan(session, scan_id)

        operation = _operation_for(session, scan_id, media_file.id)
        assert operation.planned_destination_path == absolute_nfc(
            dest_root / "iphone_photo" / "photo.jpg"
        )


def test_unmapped_group_excluded_from_plan(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        media_file = _make_media_file(session, scan_id, source)
        assert media_file.id is not None
        _make_classification(session, media_file.id, "other")
        # No DestinationRule created for "other".

        summary = generate_move_plan(session, scan_id)

        assert summary.unmapped == 1
        assert summary.total_planned == 0
        assert summary.total_blocked == 0


def test_unclassified_file_excluded_from_plan(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        source = _make_source_file(tmp_path, "photo.jpg")
        _make_media_file(session, scan_id, source)
        # No Classification created.
        _make_rule(session, scan_id, "other", str(tmp_path / "dest"))

        summary = generate_move_plan(session, scan_id)

        assert summary.skipped_unclassified == 1
        assert summary.total_planned == 0
        assert summary.total_blocked == 0


def test_generate_move_plan_never_writes_to_destination(engine: Engine, tmp_path: Path) -> None:
    with get_session(engine) as session:
        scan_id = _make_scan(session)
        planned_source = _make_source_file(tmp_path, "ok.jpg")
        blocked_source = _make_source_file(tmp_path, "collide.jpg")
        media_ok = _make_media_file(session, scan_id, planned_source)
        media_blocked = _make_media_file(session, scan_id, blocked_source)
        assert media_ok.id is not None
        assert media_blocked.id is not None
        _make_classification(session, media_ok.id, "other")
        _make_classification(session, media_blocked.id, "video")

        dest_root = tmp_path / "dest"
        (dest_root / "video").mkdir(parents=True)
        (dest_root / "video" / "collide.jpg").write_bytes(b"pre-existing")
        before = sorted(p.name for p in dest_root.rglob("*"))

        _make_rule(session, scan_id, "other", str(dest_root))
        _make_rule(session, scan_id, "video", str(dest_root))

        generate_move_plan(session, scan_id)

        after = sorted(p.name for p in dest_root.rglob("*"))
        assert after == before
