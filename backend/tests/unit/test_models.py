from pathlib import Path

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models import MediaFile, Scan


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_scan_and_media_file_round_trip_through_sqlite(engine: Engine) -> None:
    with get_session(engine) as session:
        scan = Scan(source_root="D:/Fotos", recursive=True, status="completed", total_files=2)
        session.add(scan)
        session.commit()
        session.refresh(scan)

        media_file = MediaFile(
            scan_id=scan.id,
            absolute_path="D:/Fotos/img.jpg",
            relative_path="img.jpg",
            file_name="img.jpg",
            extension=".jpg",
            mime_type="image/jpeg",
            file_type="image",
            size_bytes=1024,
            width=100,
            height=100,
            metadata_json='{"Make": "Apple"}',
            processing_status="processed",
        )
        session.add(media_file)
        session.commit()

        scan_id = scan.id
        media_file_id = media_file.id

    with get_session(engine) as session:
        reloaded_scan = session.get(Scan, scan_id)
        assert reloaded_scan is not None
        assert reloaded_scan.source_root == "D:/Fotos"
        assert reloaded_scan.recursive is True
        assert reloaded_scan.status == "completed"
        assert reloaded_scan.total_files == 2
        assert len(reloaded_scan.media_files) == 1
        assert reloaded_scan.media_files[0].id == media_file_id

        reloaded_media_file = session.get(MediaFile, media_file_id)
        assert reloaded_media_file is not None
        assert reloaded_media_file.absolute_path == "D:/Fotos/img.jpg"
        assert reloaded_media_file.mime_type == "image/jpeg"
        assert reloaded_media_file.size_bytes == 1024
        assert reloaded_media_file.metadata_json == '{"Make": "Apple"}'
        assert reloaded_media_file.scan.id == scan_id
