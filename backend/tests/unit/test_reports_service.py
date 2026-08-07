"""Unit tests for backend.app.services.reports — see
specs/2026-08-07-phase-13-thumbnails-static-reports/plan.md and validation.md.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models.classification import Classification
from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.models.scan import Scan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services.reports import (
    UNCLASSIFIED_GROUP,
    ReportRow,
    _build_rows,
    _summarize,
)
from backend.app.services.thumbnails import ThumbnailResult


def _engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_report_row_has_no_coordinate_fields() -> None:
    field_names = {field_.name for field_ in dataclasses.fields(ReportRow)}
    assert "gps_latitude" not in field_names
    assert "gps_longitude" not in field_names


def test_build_rows_joins_metadata_and_classification(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with get_session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="completed")
        )
        assert scan.id is not None

        classified = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="a.jpg",
                relative_path="a.jpg",
                file_name="a.jpg",
                extension=".jpg",
                size_bytes=100,
                processing_status="done",
                media_kind="image",
            )
        )
        assert classified.id is not None
        MediaMetadataRepository(session).create(
            MediaMetadata(
                media_file_id=classified.id,
                make="Apple",
                model="iPhone 14 Pro",
                gps_latitude=35.6762,
                gps_longitude=139.6503,
            )
        )
        ClassificationRepository(session).create(
            Classification(
                media_file_id=classified.id,
                media_kind="image",
                source_origin="iphone_photo",
                image_format="standard",
                automatic_routing_group="iphone_photo",
                effective_routing_group="iphone_photo",
                confidence=0.98,
                requires_review=False,
                reasons_json=json.dumps(["Make/Model match Apple iPhone"]),
                country_code="JP",
                country_name="Japan",
                gps_latitude=35.6762,
                gps_longitude=139.6503,
            )
        )

        unclassified = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="b.jpg",
                relative_path="b.jpg",
                file_name="b.jpg",
                extension=".jpg",
                size_bytes=50,
                processing_status="done",
                media_kind="image",
            )
        )

        media_files = [classified, unclassified]
        rows = _build_rows(session, media_files, thumbnail_results={})

    by_path = {row.relative_path: row for row in rows}

    classified_row = by_path["a.jpg"]
    assert classified_row.routing_group == "iphone_photo"
    assert classified_row.confidence == 0.98
    assert classified_row.country_code == "JP"
    assert classified_row.make == "Apple"
    assert classified_row.model == "iPhone 14 Pro"
    assert classified_row.reasons == ["Make/Model match Apple iPhone"]
    assert classified_row.manual_override is False
    assert classified_row.thumbnail_path is None

    unclassified_row = by_path["b.jpg"]
    assert unclassified_row.routing_group == UNCLASSIFIED_GROUP
    assert unclassified_row.confidence is None
    assert unclassified_row.country_code is None

    for row in rows:
        assert not hasattr(row, "gps_latitude")
        assert not hasattr(row, "gps_longitude")


def test_build_rows_marks_manual_override(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with get_session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="completed")
        )
        assert scan.id is not None
        media = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="a.jpg",
                relative_path="a.jpg",
                file_name="a.jpg",
                extension=".jpg",
                size_bytes=1,
                processing_status="done",
                media_kind="image",
            )
        )
        assert media.id is not None
        ClassificationRepository(session).create(
            Classification(
                media_file_id=media.id,
                media_kind="image",
                source_origin="other",
                image_format="standard",
                automatic_routing_group="other",
                manual_routing_group="iphone_raw",
                effective_routing_group="iphone_raw",
                confidence=0.2,
                requires_review=True,
                reasons_json="[]",
            )
        )

        rows = _build_rows(session, [media], thumbnail_results={})

    assert rows[0].manual_override is True
    assert rows[0].routing_group == "iphone_raw"


def test_build_rows_includes_thumbnail_path_only_on_success(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    with get_session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="completed")
        )
        assert scan.id is not None
        saved = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="a.jpg",
                relative_path="a.jpg",
                file_name="a.jpg",
                extension=".jpg",
                size_bytes=1,
                processing_status="done",
                media_kind="image",
            )
        )
        assert saved.id is not None

        success_result = {saved.id: ThumbnailResult(success=True)}
        rows = _build_rows(session, [saved], thumbnail_results=success_result)
        assert rows[0].thumbnail_path == f"thumbnails/{saved.id}.jpg"

        failed_result = {saved.id: ThumbnailResult(success=False, error_code="X")}
        rows = _build_rows(session, [saved], thumbnail_results=failed_result)
        assert rows[0].thumbnail_path is None


def test_summarize_computes_totals_and_flags() -> None:
    rows = [
        ReportRow(
            media_file_id=1,
            relative_path="a.jpg",
            media_kind="image",
            extension=".jpg",
            size_bytes=100,
            width=None,
            height=None,
            duration_seconds=None,
            capture_datetime=None,
            make=None,
            model=None,
            software=None,
            lens_model=None,
            routing_group="iphone_photo",
            source_origin="iphone_photo",
            image_format="standard",
            confidence=0.9,
            requires_review=False,
            reasons=[],
            country_code="JP",
            country_name="Japan",
            manual_override=False,
            error_code=None,
            error_message=None,
            thumbnail_path="thumbnails/1.jpg",
        ),
        ReportRow(
            media_file_id=2,
            relative_path="b.mp4",
            media_kind="video",
            extension=".mp4",
            size_bytes=200,
            width=None,
            height=None,
            duration_seconds=1.0,
            capture_datetime=None,
            make=None,
            model=None,
            software=None,
            lens_model=None,
            routing_group="video",
            source_origin="video",
            image_format="not_applicable",
            confidence=0.4,
            requires_review=True,
            reasons=[],
            country_code=None,
            country_name=None,
            manual_override=False,
            error_code="VIDEO_UNREADABLE",
            error_message="no video stream",
            thumbnail_path=None,
        ),
    ]
    thumbnail_results = {1: ThumbnailResult(success=True), 2: ThumbnailResult(success=False)}

    summary = _summarize(rows, thumbnail_results)

    assert summary.total_files == 2
    assert summary.total_bytes == 300
    assert summary.thumbnails_generated == 1
    assert summary.thumbnails_failed == 1
    assert summary.low_confidence_count == 1
    assert summary.error_count == 1
    assert summary.totals_by_group == {"iphone_photo": 1, "video": 1}
    assert summary.totals_by_country == {"JP": 1}
