"""`Classification` table round-trip — see
specs/2026-08-07-phase-8-rule-engine-core/plan.md and validation.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models import Classification, MediaFile, Scan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.scan_repository import ScanRepository


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_classification_round_trips_through_sqlite(engine: Engine) -> None:
    with get_session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="D:/Fotos", recursive=True, status="completed")
        )
        media_file = MediaFileRepository(session).create(
            MediaFile(
                scan_id=scan.id,
                absolute_path="D:/Fotos/img.jpg",
                relative_path="img.jpg",
                file_name="img.jpg",
                extension=".jpg",
                size_bytes=1024,
                processing_status="pending",
            )
        )
        assert media_file.id is not None

        classification = ClassificationRepository(session).create(
            Classification(
                media_file_id=media_file.id,
                media_kind="image",
                source_origin="iphone_camera",
                image_format="standard",
                automatic_routing_group="iphone_photo",
                effective_routing_group="iphone_photo",
                confidence=0.95,
                requires_review=False,
                reasons_json=json.dumps(["EXIF Make=Apple"]),
                device_make="Apple",
                device_model="iPhone 14 Pro",
            )
        )
        classification_id = classification.id
        media_file_id = media_file.id

    with get_session(engine) as session:
        reloaded = session.get(Classification, classification_id)
        assert reloaded is not None
        assert reloaded.effective_routing_group == "iphone_photo"
        assert reloaded.manual_routing_group is None
        assert reloaded.media_file.id == media_file_id

        via_repository = ClassificationRepository(session).get_by_media_file_id(media_file_id)
        assert via_repository is not None
        assert via_repository.id == classification_id
