"""Unit tests for the job-triggering API routes — README §25/§26, roadmap Phase 18."""

from __future__ import annotations

import json
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
from backend.app.core.tools import ToolNotAvailableError
from backend.app.models.job import Job
from backend.app.models.scan import Scan
from backend.app.repositories.job_repository import JobRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services import job_runner as job_runner_module

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


@pytest.fixture(autouse=True)
def _assume_required_tools_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(job_runner_module, "require_tools", lambda *_names: None)


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


def _wait_for_terminal(client: TestClient, job_id: int, timeout: float = 10.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"job_id={job_id} did not reach a terminal state in {timeout}s")


def test_post_scans_queues_and_completes(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", source / "iphone_jpeg_gps.jpg")

    response = client.post("/api/scans", json={"source_root": str(source), "recursive": True})

    assert response.status_code == 202
    body = response.json()
    assert body["status"] in ("queued", "running")

    finished = _wait_for_terminal(client, body["id"])
    assert finished["status"] == "completed"
    assert finished["scan_id"] is not None

    scan_response = client.get(f"/api/scans/{finished['scan_id']}")
    assert scan_response.status_code == 200
    assert scan_response.json()["total_files"] == 1


def test_post_scans_invalid_path_returns_400(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/scans", json={"source_root": str(tmp_path / "does-not-exist")})
    assert response.status_code == 400


def test_post_classify_unknown_scan_returns_404(client: TestClient) -> None:
    response = client.post("/api/scans/999/classify")
    assert response.status_code == 404


def test_post_classify_rejects_incomplete_scan(client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="running")
        )
        assert scan.id is not None

    response = client.post(f"/api/scans/{scan.id}/classify")

    assert response.status_code == 409
    assert "must be completed" in response.json()["detail"]


def test_post_classify_rejects_second_active_job(client: TestClient, engine: Engine) -> None:
    with Session(engine) as session:
        scan = ScanRepository(session).create(
            Scan(source_root="X", recursive=True, status="completed")
        )
        assert scan.id is not None
        scan_id = scan.id
        JobRepository(session).create(
            Job(job_type="classify", scan_id=scan_id, status="running", params_json="{}")
        )

    response = client.post(f"/api/scans/{scan_id}/classify")

    assert response.status_code == 409
    assert "already has an active job" in response.json()["detail"]


def test_post_classify_happy_path(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", source / "iphone_jpeg_gps.jpg")

    scan_response = client.post("/api/scans", json={"source_root": str(source)})
    scan_job = _wait_for_terminal(client, scan_response.json()["id"])
    scan_id = scan_job["scan_id"]

    classify_response = client.post(f"/api/scans/{scan_id}/classify")
    assert classify_response.status_code == 202

    classify_job = _wait_for_terminal(client, classify_response.json()["id"])
    assert classify_job["status"] == "completed"

    files_response = client.get(f"/api/scans/{scan_id}/files")
    file_id = files_response.json()[0]["id"]
    classification_response = client.get(f"/api/files/{file_id}/classification")
    assert classification_response.status_code == 200


def test_cancel_with_no_active_job_returns_404(client: TestClient) -> None:
    response = client.post("/api/scans/999/cancel")
    assert response.status_code == 404


def test_get_job_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/999")
    assert response.status_code == 404


def test_job_events_stream_reaches_terminal_state(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", source / "iphone_jpeg_gps.jpg")

    scan_response = client.post("/api/scans", json={"source_root": str(source)})
    job_id = scan_response.json()["id"]

    last_event: dict[str, object] | None = None
    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            last_event = json.loads(line[len("data: ") :])
            if last_event["status"] in TERMINAL_STATUSES:
                break

    assert last_event is not None
    assert last_event["status"] == "completed"


def test_job_events_stream_exposes_missing_tool_failure(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()

    def _missing_tool(*_names: str) -> None:
        raise ToolNotAvailableError("ffprobe", "ffprobe is unavailable")

    monkeypatch.setattr(job_runner_module, "require_tools", _missing_tool)
    scan_response = client.post("/api/scans", json={"source_root": str(source)})
    job_id = scan_response.json()["id"]

    last_event: dict[str, object] | None = None
    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            last_event = json.loads(line[len("data: ") :])
            if last_event["status"] in TERMINAL_STATUSES:
                break

    assert last_event is not None
    assert last_event["status"] == "failed"
    assert last_event["error_code"] == "TOOL_NOT_AVAILABLE"
    assert last_event["error_message"] == "ffprobe is unavailable"
    assert last_event["scan_id"] is None


def test_job_events_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/api/jobs/999/events")
    assert response.status_code == 404
