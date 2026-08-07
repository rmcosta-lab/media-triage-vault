"""Integration test: launch-scan -> watch -> classify -> watch -> read-back,
entirely through the API — README §26, roadmap Phase 18's done criterion.
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.api.app import create_app
from backend.app.api.deps import get_session_dependency, get_thumbnail_cache_dir_dependency
from backend.app.core.db import create_db_and_tables, get_engine

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

ALL_FIXTURES = (
    "iphone_jpeg_gps.jpg",
    "iphone_heic.heic",
    "jpeg_no_exif.jpg",
    "Screenshot_20260730-152000.png",
    "IMG-20260730-WA0001.jpg",
    "sample_video.mp4",
)

TERMINAL_STATUSES = ("completed", "failed", "cancelled")


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


def _wait_for_terminal(client: TestClient, job_id: int, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"job_id={job_id} did not reach a terminal state in {timeout}s")


def test_launch_scan_watch_classify_watch_read_back(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ALL_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, source / name)

    scan_response = client.post("/api/scans", json={"source_root": str(source), "recursive": True})
    assert scan_response.status_code == 202
    scan_job_id = scan_response.json()["id"]

    scan_job = _wait_for_terminal(client, scan_job_id)
    assert scan_job["status"] == "completed"
    scan_id = scan_job["scan_id"]
    assert scan_id is not None

    scan_detail = client.get(f"/api/scans/{scan_id}")
    assert scan_detail.status_code == 200
    assert scan_detail.json()["total_files"] == len(ALL_FIXTURES)

    classify_response = client.post(f"/api/scans/{scan_id}/classify")
    assert classify_response.status_code == 202
    classify_job = _wait_for_terminal(client, classify_response.json()["id"])
    assert classify_job["status"] == "completed"

    files = client.get(f"/api/scans/{scan_id}/files").json()
    assert len(files) == len(ALL_FIXTURES)

    whatsapp_file = next(f for f in files if f["file_name"] == "IMG-20260730-WA0001.jpg")
    classification = client.get(f"/api/files/{whatsapp_file['id']}/classification")
    assert classification.status_code == 200
    assert classification.json()["effective_routing_group"] == "whatsapp_received"
