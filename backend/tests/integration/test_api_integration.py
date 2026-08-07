"""Integration test: read the real `scan` -> `classify` CLI pipeline back
through the read-only API — README §25, roadmap Phase 17.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from typer.testing import CliRunner

from backend.app.api.app import create_app
from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.cli.main import app as cli_app
from backend.app.core.db import get_engine

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

ALL_FIXTURES = (
    "iphone_jpeg_gps.jpg",
    "iphone_heic.heic",
    "jpeg_no_exif.jpg",
    "Screenshot_20260730-152000.png",
    "IMG-20260730-WA0001.jpg",
    "sample_video.mp4",
)

runner = CliRunner()


@pytest.fixture
def scanned_database(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    for name in ALL_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, source / name)

    database = tmp_path / "test.db"
    output = tmp_path / "report"

    scan_result = runner.invoke(
        cli_app, ["scan", str(source), "--output", str(output), "--database", str(database)]
    )
    assert scan_result.exit_code == 0, scan_result.output

    classify_result = runner.invoke(
        cli_app, ["classify", "--scan-id", "1", "--database", str(database)]
    )
    assert classify_result.exit_code == 0, classify_result.output

    return database


@pytest.fixture
def client(scanned_database: Path, tmp_path: Path) -> Iterator[TestClient]:
    engine = get_engine(scanned_database)
    app = create_app()

    def _session_override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    thumbnail_cache_dir = tmp_path / "api_thumbnails"

    def _thumbnail_dir_override() -> Path:
        thumbnail_cache_dir.mkdir(parents=True, exist_ok=True)
        return thumbnail_cache_dir

    app.dependency_overrides[get_session_dependency] = _session_override
    app.dependency_overrides[get_thumbnail_cache_dir_dependency] = _thumbnail_dir_override

    with TestClient(app) as test_client:
        yield test_client


def test_scan_and_files_match_cli_pipeline(client: TestClient) -> None:
    scan_response = client.get("/api/scans/1")
    assert scan_response.status_code == 200
    assert scan_response.json()["total_files"] == len(ALL_FIXTURES)

    files_response = client.get("/api/scans/1/files")
    assert files_response.status_code == 200
    files = files_response.json()
    assert len(files) == len(ALL_FIXTURES)
    assert {entry["file_name"] for entry in files} == set(ALL_FIXTURES)


def test_whatsapp_fixture_classification_via_api(client: TestClient) -> None:
    files = client.get("/api/scans/1/files").json()
    whatsapp_file = next(f for f in files if f["file_name"] == "IMG-20260730-WA0001.jpg")

    classification_response = client.get(f"/api/files/{whatsapp_file['id']}/classification")

    assert classification_response.status_code == 200
    body = classification_response.json()
    assert body["effective_routing_group"] == "whatsapp_received"
    assert "gps_latitude" not in body


def test_thumbnail_endpoint_serves_a_real_fixture(client: TestClient) -> None:
    files = client.get("/api/scans/1/files").json()
    photo = next(f for f in files if f["file_name"] == "iphone_jpeg_gps.jpg")

    response = client.get(f"/api/files/{photo['id']}/thumbnail")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert len(response.content) > 0
