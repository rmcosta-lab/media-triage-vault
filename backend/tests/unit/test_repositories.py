from pathlib import Path

import pytest
from sqlalchemy import Engine

from backend.app.core.db import create_db_and_tables, get_engine, get_session
from backend.app.models import MediaFile, Scan
from backend.app.repositories import MediaFileRepository, ScanRepository


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def test_scan_repository_crud(engine: Engine) -> None:
    with get_session(engine) as session:
        repo = ScanRepository(session)

        created = repo.create(Scan(source_root="D:/Fotos", recursive=True, status="pending"))
        assert created.id is not None

        fetched = repo.get(created.id)
        assert fetched is not None
        assert fetched.source_root == "D:/Fotos"

        fetched.processed_files = 5
        updated = repo.update(fetched)
        assert updated.processed_files == 5

        assert [scan.id for scan in repo.list()] == [created.id]

        repo.delete(created.id)
        assert repo.get(created.id) is None
        assert repo.list() == []


def test_media_file_repository_crud_and_list_by_scan(engine: Engine) -> None:
    with get_session(engine) as session:
        scan_repo = ScanRepository(session)
        media_file_repo = MediaFileRepository(session)

        scan = scan_repo.create(Scan(source_root="D:/Fotos", recursive=True, status="pending"))
        other_scan = scan_repo.create(
            Scan(source_root="D:/Other", recursive=False, status="pending")
        )
        assert scan.id is not None
        assert other_scan.id is not None

        created = media_file_repo.create(
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
        media_file_repo.create(
            MediaFile(
                scan_id=other_scan.id,
                absolute_path="D:/Other/img2.jpg",
                relative_path="img2.jpg",
                file_name="img2.jpg",
                extension=".jpg",
                size_bytes=2048,
                processing_status="pending",
            )
        )
        assert created.id is not None

        fetched = media_file_repo.get(created.id)
        assert fetched is not None
        assert fetched.absolute_path == "D:/Fotos/img.jpg"

        fetched.processing_status = "processed"
        updated = media_file_repo.update(fetched)
        assert updated.processing_status == "processed"

        only_first_scan = media_file_repo.list_by_scan(scan.id)
        assert [media_file.id for media_file in only_first_scan] == [created.id]

        media_file_repo.delete(created.id)
        assert media_file_repo.get(created.id) is None
        assert media_file_repo.list_by_scan(scan.id) == []
