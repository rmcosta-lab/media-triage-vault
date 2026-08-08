"""Unit tests for the destinations/move-plan/execute API routes — README §25,
roadmap Phase 19.
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
from backend.app.models.job import Job
from backend.app.repositories.job_repository import JobRepository
from backend.app.rules.engine import ROUTING_GROUPS
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


def _wait_for_terminal(client: TestClient, url: str, timeout: float = 15.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(url)
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"{url} did not reach a terminal state in {timeout}s")


@pytest.fixture
def scanned_and_classified(client: TestClient, tmp_path: Path) -> tuple[int, Path]:
    """Scan + classify a small real fixture set through the API. Returns (scan_id, dest_root)."""
    source = tmp_path / "source"
    source.mkdir()
    shutil.copy(FIXTURES_DIR / "iphone_jpeg_gps.jpg", source / "iphone_jpeg_gps.jpg")
    shutil.copy(FIXTURES_DIR / "jpeg_no_exif.jpg", source / "jpeg_no_exif.jpg")

    scan_response = client.post("/api/scans", json={"source_root": str(source)})
    scan_job = _wait_for_terminal(client, f"/api/jobs/{scan_response.json()['id']}")
    scan_id = scan_job["scan_id"]

    classify_response = client.post(f"/api/scans/{scan_id}/classify")
    _wait_for_terminal(client, f"/api/jobs/{classify_response.json()['id']}")

    return scan_id, tmp_path / "dest"


def test_put_destinations_happy_path(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, dest_root = scanned_and_classified
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}

    response = client.put(f"/api/scans/{scan_id}/destinations", json=mapping)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(ROUTING_GROUPS)


def test_put_destinations_unknown_group_returns_400(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, dest_root = scanned_and_classified
    response = client.put(
        f"/api/scans/{scan_id}/destinations",
        json={"not_a_group": {"destination_root": str(dest_root)}},
    )
    assert response.status_code == 400


def test_put_destinations_missing_scan_returns_404(client: TestClient, tmp_path: Path) -> None:
    response = client.put(
        "/api/scans/999/destinations",
        json={"other": {"destination_root": str(tmp_path / "dest")}},
    )
    assert response.status_code == 404


def test_move_plan_happy_path_and_missing_scan(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, dest_root = scanned_and_classified
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}
    client.put(f"/api/scans/{scan_id}/destinations", json=mapping)

    response = client.post(f"/api/scans/{scan_id}/move-plan", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["total_planned"] >= 1
    assert len(body["operations"]) >= 1
    assert all(
        Path(operation["planned_destination_path"]).parent.name in ROUTING_GROUPS
        for operation in body["operations"]
    )

    missing = client.post("/api/scans/999/move-plan", json={})
    assert missing.status_code == 404


def test_get_move_plan_missing_returns_404(client: TestClient) -> None:
    response = client.get("/api/move-plans/999")
    assert response.status_code == 404


def test_execute_requires_approval(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, dest_root = scanned_and_classified
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}
    client.put(f"/api/scans/{scan_id}/destinations", json=mapping)
    plan = client.post(f"/api/scans/{scan_id}/move-plan", json={}).json()

    unapproved = client.post(f"/api/move-plans/{plan['id']}/execute")
    assert unapproved.status_code == 400

    approve_response = client.post(f"/api/move-plans/{plan['id']}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["approved_at"] is not None

    execute_response = client.post(f"/api/move-plans/{plan['id']}/execute")
    assert execute_response.status_code == 202


def test_execute_rejects_a_second_active_job(
    client: TestClient,
    engine: Engine,
    scanned_and_classified: tuple[int, Path],
) -> None:
    scan_id, dest_root = scanned_and_classified
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}
    client.put(f"/api/scans/{scan_id}/destinations", json=mapping)
    plan = client.post(f"/api/scans/{scan_id}/move-plan", json={}).json()
    client.post(f"/api/move-plans/{plan['id']}/approve")

    with Session(engine) as session:
        JobRepository(session).create(
            Job(
                job_type="execute",
                move_plan_id=plan["id"],
                status="running",
                params_json="{}",
            )
        )

    response = client.post(f"/api/move-plans/{plan['id']}/execute")

    assert response.status_code == 409
    assert "already has an active execution" in response.json()["detail"]


def test_full_execute_flow_moves_a_real_file(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, dest_root = scanned_and_classified
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}
    client.put(f"/api/scans/{scan_id}/destinations", json=mapping)
    plan = client.post(f"/api/scans/{scan_id}/move-plan", json={}).json()
    client.post(f"/api/move-plans/{plan['id']}/approve")

    execute_response = client.post(f"/api/move-plans/{plan['id']}/execute")
    assert execute_response.status_code == 202
    run_id = execute_response.json()["id"]

    finished_run = _wait_for_terminal(client, f"/api/move-runs/{run_id}")
    assert finished_run["status"] == "completed"

    report = client.get(f"/api/move-runs/{run_id}/report")
    assert report.status_code == 200
    report_body = report.json()
    assert report_body["totals"]["completed"] == plan["total_planned"]

    updated_plan = client.get(f"/api/move-plans/{plan['id']}").json()
    completed_ops = [op for op in updated_plan["operations"] if op["status"] == "completed"]
    assert completed_ops
    for operation in completed_ops:
        assert Path(operation["actual_destination_path"]).exists()
        assert not Path(operation["source_path"]).exists()


def test_move_run_and_cancel_missing_return_404(client: TestClient) -> None:
    assert client.get("/api/move-runs/999").status_code == 404
    assert client.post("/api/move-runs/999/cancel").status_code == 404


def test_scan_report_excludes_coordinates(
    client: TestClient, scanned_and_classified: tuple[int, Path]
) -> None:
    scan_id, _dest_root = scanned_and_classified

    response = client.get(f"/api/scans/{scan_id}/report")

    assert response.status_code == 200
    body_text = response.text
    for coordinate_field in ("gps_latitude", "gps_longitude", "gps_position_raw"):
        assert coordinate_field not in body_text


def test_scan_report_missing_scan_returns_404(client: TestClient) -> None:
    response = client.get("/api/scans/999/report")
    assert response.status_code == 404
