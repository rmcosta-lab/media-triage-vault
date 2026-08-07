"""Unit tests for backend.app.cli.scan_report — see
specs/2026-08-07-phase-7-scan-cli/plan.md and validation.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import Engine

from backend.app.cli.scan_report import write_error_log, write_inventory_json
from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.models.scan import Scan
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository


def test_write_error_log_writes_only_errored_rows(tmp_path: Path) -> None:
    ok_row = MediaFile(
        scan_id=1,
        absolute_path="a.jpg",
        relative_path="a.jpg",
        file_name="a.jpg",
        extension=".jpg",
        size_bytes=1,
        processing_status="pending",
    )
    errored_row = MediaFile(
        scan_id=1,
        absolute_path="b.mp4",
        relative_path="b.mp4",
        file_name="b.mp4",
        extension=".mp4",
        size_bytes=1,
        processing_status="error",
        error_code="VIDEO_UNREADABLE",
        error_message="no video stream",
    )

    log_path = tmp_path / "errors.log"
    count = write_error_log(log_path, [ok_row, errored_row])

    assert count == 1
    content = log_path.read_text(encoding="utf-8")
    assert "a.jpg" not in content
    assert "b.mp4: VIDEO_UNREADABLE — no video stream" in content


def test_write_error_log_empty_when_no_errors(tmp_path: Path) -> None:
    ok_row = MediaFile(
        scan_id=1,
        absolute_path="a.jpg",
        relative_path="a.jpg",
        file_name="a.jpg",
        extension=".jpg",
        size_bytes=1,
        processing_status="pending",
    )
    log_path = tmp_path / "errors.log"
    count = write_error_log(log_path, [ok_row])
    assert count == 0
    assert log_path.read_text(encoding="utf-8") == ""


def _engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_write_inventory_json_nests_metadata_when_present(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with get_session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="completed")
        )
        assert scan.id is not None

        with_metadata = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="a.jpg",
                relative_path="a.jpg",
                file_name="a.jpg",
                extension=".jpg",
                size_bytes=1,
                processing_status="pending",
            )
        )
        assert with_metadata.id is not None
        MediaMetadataRepository(session).create(
            MediaMetadata(
                media_file_id=with_metadata.id,
                make="Apple",
                gps_latitude=35.6762,
                gps_longitude=139.6503,
                gps_position_raw="35.6762 139.6503",
                location_information="+35.6762+139.6503/",
            )
        )

        without_metadata = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="b.jpg",
                relative_path="b.jpg",
                file_name="b.jpg",
                extension=".jpg",
                size_bytes=1,
                processing_status="pending",
            )
        )

        out_path = tmp_path / "inventory.json"
        write_inventory_json(out_path, session, [with_metadata, without_metadata])

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data) == 2
    by_name = {entry["file_name"]: entry for entry in data}
    assert by_name["a.jpg"]["metadata"]["make"] == "Apple"
    assert by_name["b.jpg"]["metadata"] is None

    # README §14.4/§28 — coordinates never appear in the default JSON export.
    exported_metadata_keys = set(by_name["a.jpg"]["metadata"])
    assert "gps_latitude" not in exported_metadata_keys
    assert "gps_longitude" not in exported_metadata_keys
    assert "gps_position_raw" not in exported_metadata_keys
    assert "location_information" not in exported_metadata_keys
