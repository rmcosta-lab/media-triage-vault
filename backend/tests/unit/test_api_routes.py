"""Unit tests for the read-only API routes — README §25, roadmap Phase 17."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.api.app import create_app
from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.core.db import create_db_and_tables, get_engine
from backend.app.core.paths import absolute_nfc
from backend.app.models.classification import Classification
from backend.app.models.media_file import MediaFile
from backend.app.models.media_metadata import MediaMetadata
from backend.app.models.scan import Scan
from backend.app.repositories.classification_repository import ClassificationRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.media_metadata_repository import MediaMetadataRepository
from backend.app.repositories.scan_repository import ScanRepository

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


@pytest.fixture
def client(engine: Engine, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app()

    def _session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    thumbnail_cache_dir = tmp_path / "thumbnails"

    def _thumbnail_dir_override() -> Path:
        thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)
        return thumbnail_cache_dir

    app.dependency_overrides[get_session_dependency] = _session_override
    app.dependency_overrides[get_thumbnail_cache_dir_dependency] = _thumbnail_dir_override

    with TestClient(app) as test_client:
        yield test_client


def _seed_scan(session: Session) -> int:
    scan = ScanRepository(session).create(
        Scan(
            source_root="D:/Fotos",
            recursive=True,
            status="completed",
            total_files=1,
            processed_files=1,
            total_bytes=123,
        )
    )
    assert scan.id is not None
    return scan.id


def _seed_media_file(session: Session, scan_id: int, tmp_path: Path, name: str) -> MediaFile:
    source = tmp_path / name
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", source)
    stat_result = source.stat()
    return MediaFileRepository(session).create(
        MediaFile(
            scan_id=scan_id,
            absolute_path=absolute_nfc(source),
            relative_path=name,
            file_name=name,
            extension=".jpg",
            media_kind="image",
            size_bytes=stat_result.st_size,
            modified_at=datetime.fromtimestamp(stat_result.st_mtime, tz=UTC),
            processing_status="processed",
        )
    )


def test_get_scan_happy_path(client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)

    response = client.get(f"/api/scans/{scan_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == scan_id
    assert body["status"] == "completed"


def test_get_scan_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/scans/999")
    assert response.status_code == 404


def test_list_scan_files_happy_path_and_pagination(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        for index in range(3):
            _seed_media_file(session, scan_id, tmp_path, f"photo_{index}.jpg")

    response = client.get(f"/api/scans/{scan_id}/files")
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert "absolute_path" not in response.json()[0]

    paged = client.get(f"/api/scans/{scan_id}/files", params={"skip": 1, "limit": 1})
    assert paged.status_code == 200
    assert len(paged.json()) == 1


def test_list_scan_files_missing_scan_returns_404(client: TestClient) -> None:
    response = client.get("/api/scans/999/files")
    assert response.status_code == 404


def test_get_file_classification_happy_path_excludes_coordinates(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        assert media_file.id is not None
        ClassificationRepository(session).create(
            Classification(
                media_file_id=media_file.id,
                media_kind="image",
                source_origin="iphone",
                image_format="standard",
                automatic_routing_group="iphone_photo",
                effective_routing_group="iphone_photo",
                confidence=0.95,
                requires_review=False,
                reasons_json="[]",
                gps_latitude=35.0,
                gps_longitude=139.0,
                country_code="JP",
                country_name="Japan",
            )
        )
        file_id = media_file.id

    response = client.get(f"/api/files/{file_id}/classification")

    assert response.status_code == 200
    body = response.json()
    assert body["country_code"] == "JP"
    assert "gps_latitude" not in body
    assert "gps_longitude" not in body


def test_get_file_classification_missing_file_returns_404(client: TestClient) -> None:
    response = client.get("/api/files/999/classification")
    assert response.status_code == 404


def test_get_file_classification_no_classification_yet_returns_404(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        file_id = media_file.id

    response = client.get(f"/api/files/{file_id}/classification")
    assert response.status_code == 404


def test_patch_file_classification_overrides_and_persists(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        assert media_file.id is not None
        ClassificationRepository(session).create(
            Classification(
                media_file_id=media_file.id,
                media_kind="image",
                source_origin="iphone",
                image_format="standard",
                automatic_routing_group="iphone_photo",
                effective_routing_group="iphone_photo",
                confidence=0.95,
                requires_review=False,
                reasons_json="[]",
            )
        )
        file_id = media_file.id

    response = client.patch(f"/api/files/{file_id}/classification", json={"routing_group": "other"})

    assert response.status_code == 200
    body = response.json()
    assert body["manual_routing_group"] == "other"
    assert body["effective_routing_group"] == "other"
    assert body["automatic_routing_group"] == "iphone_photo"
    assert body["override_timestamp"] is not None

    persisted = client.get(f"/api/files/{file_id}/classification").json()
    assert persisted["effective_routing_group"] == "other"
    assert persisted["manual_routing_group"] == "other"


def test_patch_file_classification_invalid_group_returns_400(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        assert media_file.id is not None
        ClassificationRepository(session).create(
            Classification(
                media_file_id=media_file.id,
                media_kind="image",
                source_origin="other",
                image_format="standard",
                automatic_routing_group="other",
                effective_routing_group="other",
                confidence=0.5,
                requires_review=True,
                reasons_json="[]",
            )
        )
        file_id = media_file.id

    response = client.patch(
        f"/api/files/{file_id}/classification", json={"routing_group": "not_a_group"}
    )
    assert response.status_code == 400


def test_patch_file_classification_missing_classification_returns_404(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        file_id = media_file.id

    response = client.patch(f"/api/files/{file_id}/classification", json={"routing_group": "other"})
    assert response.status_code == 404


def test_get_file_metadata_happy_path_excludes_coordinates(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        assert media_file.id is not None
        MediaMetadataRepository(session).create(
            MediaMetadata(
                media_file_id=media_file.id,
                make="Apple",
                model="iPhone 15",
                gps_latitude=35.0,
                gps_longitude=139.0,
                gps_position_raw="35.0, 139.0",
                location_information="+35.000-139.000/",
            )
        )
        file_id = media_file.id

    response = client.get(f"/api/files/{file_id}/metadata")

    assert response.status_code == 200
    body = response.json()
    assert body["make"] == "Apple"
    for coordinate_field in (
        "gps_latitude",
        "gps_longitude",
        "gps_position_raw",
        "location_information",
    ):
        assert coordinate_field not in body


def test_get_file_metadata_missing_file_returns_404(client: TestClient) -> None:
    response = client.get("/api/files/999/metadata")
    assert response.status_code == 404


def test_get_file_thumbnail_generates_then_caches(
    client: TestClient, engine: Engine, tmp_path: Path
) -> None:
    with Session(engine) as session:
        scan_id = _seed_scan(session)
        media_file = _seed_media_file(session, scan_id, tmp_path, "photo.jpg")
        file_id = media_file.id

    first = client.get(f"/api/files/{file_id}/thumbnail")
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"

    cache_dir = tmp_path / "thumbnails"
    cached_file = cache_dir / f"{file_id}.jpg"
    assert cached_file.exists()
    mtime_after_first = cached_file.stat().st_mtime

    second = client.get(f"/api/files/{file_id}/thumbnail")
    assert second.status_code == 200
    assert second.content == first.content
    assert cached_file.stat().st_mtime == mtime_after_first


def test_get_file_thumbnail_missing_file_returns_404(client: TestClient) -> None:
    response = client.get("/api/files/999/thumbnail")
    assert response.status_code == 404


def test_docs_disabled_openapi_enabled(client: TestClient) -> None:
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 200


def test_cors_allows_local_frontend_origin(client: TestClient) -> None:
    response = client.get("/api/scans/999", headers={"Origin": "http://localhost:3000"})
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_rejects_non_local_origin(client: TestClient) -> None:
    response = client.get("/api/scans/999", headers={"Origin": "https://example.com"})
    assert "access-control-allow-origin" not in response.headers
