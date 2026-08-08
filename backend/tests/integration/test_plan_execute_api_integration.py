"""Integration test: the full US-001->US-004 flow entirely over HTTP —
scan -> classify -> destinations -> move-plan -> approve -> execute -> report,
roadmap Phase 19's done criterion.
"""

from __future__ import annotations

import hashlib
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
from backend.app.rules.engine import ROUTING_GROUPS

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


def _wait_for_terminal(client: TestClient, url: str, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(url)
        assert response.status_code == 200
        body: dict[str, Any] = response.json()
        if body["status"] in TERMINAL_STATUSES:
            return body
        time.sleep(0.05)
    raise TimeoutError(f"{url} did not reach a terminal state in {timeout}s")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_full_us001_to_us004_flow_over_http(client: TestClient, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for name in ALL_FIXTURES:
        shutil.copy(FIXTURES_DIR / name, source / name)
    source_hashes = {name: _sha256(source / name) for name in ALL_FIXTURES}

    # US-001: scan
    scan_response = client.post("/api/scans", json={"source_root": str(source)})
    assert scan_response.status_code == 202
    scan_job = _wait_for_terminal(client, f"/api/jobs/{scan_response.json()['id']}")
    assert scan_job["status"] == "completed"
    scan_id = scan_job["scan_id"]

    scan_detail = client.get(f"/api/scans/{scan_id}").json()
    assert scan_detail["total_files"] == len(ALL_FIXTURES)

    # US-002: classify
    classify_response = client.post(f"/api/scans/{scan_id}/classify")
    assert classify_response.status_code == 202
    classify_job = _wait_for_terminal(client, f"/api/jobs/{classify_response.json()['id']}")
    assert classify_job["status"] == "completed"

    # US-003: destinations + move-plan
    dest_root = tmp_path / "dest"
    mapping = {group: {"destination_root": str(dest_root)} for group in ROUTING_GROUPS}
    destinations_response = client.put(f"/api/scans/{scan_id}/destinations", json=mapping)
    assert destinations_response.status_code == 200

    plan_response = client.post(f"/api/scans/{scan_id}/move-plan", json={})
    assert plan_response.status_code == 201
    plan = plan_response.json()
    assert not dest_root.exists()  # dry run: nothing created yet

    # US-004: approve + execute + report
    approve_response = client.post(f"/api/move-plans/{plan['id']}/approve")
    assert approve_response.status_code == 200

    execute_response = client.post(f"/api/move-plans/{plan['id']}/execute")
    assert execute_response.status_code == 202
    run_id = execute_response.json()["id"]

    finished_run = _wait_for_terminal(client, f"/api/move-runs/{run_id}")
    assert finished_run["status"] == "completed"

    move_report = client.get(f"/api/move-runs/{run_id}/report").json()
    assert move_report["totals"]["completed"] == plan["total_planned"]

    final_plan = client.get(f"/api/move-plans/{plan['id']}").json()
    for operation in final_plan["operations"]:
        if operation["status"] != "completed":
            continue
        destination = Path(operation["actual_destination_path"])
        assert destination.exists()
        assert destination.parent.name in ROUTING_GROUPS
        source_name = Path(operation["source_path"]).name
        assert _sha256(destination) == source_hashes[source_name]
        assert not Path(operation["source_path"]).exists()
