"""Unit tests for the background job runner — README §26, roadmap Phase 18."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.db import create_db_and_tables, get_engine
from backend.app.models.job import Job
from backend.app.repositories.job_repository import JobRepository
from backend.app.repositories.scan_repository import ScanRepository
from backend.app.services import job_runner as job_runner_module
from backend.app.services.job_runner import submit_classify_job, submit_scan_job

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
TERMINAL_STATUSES = ("completed", "failed", "cancelled")


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    engine = get_engine(tmp_path / "test.db")
    create_db_and_tables(engine)
    return engine


def _wait_for_terminal(engine: Engine, job_id: int, timeout: float = 10.0) -> Job:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with Session(engine) as session:
            job = JobRepository(session).get(job_id)
            if job is not None and job.status in TERMINAL_STATUSES:
                return job
        time.sleep(0.05)
    raise TimeoutError(f"job_id={job_id} did not reach a terminal state in {timeout}s")


def _copy_fixtures(destination: Path, names: tuple[str, ...]) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copy(FIXTURES_DIR / name, destination / name)


def test_scan_job_completes_and_stamps_scan_id(engine: Engine, tmp_path: Path) -> None:
    source = tmp_path / "source"
    _copy_fixtures(source, ("iphone_jpeg_gps.jpg", "sample_video.mp4"))

    with Session(engine) as session:
        job = submit_scan_job(session, str(source), True)
        job_id = job.id
    assert job_id is not None

    finished = _wait_for_terminal(engine, job_id)

    assert finished.status == "completed"
    assert finished.scan_id is not None

    with Session(engine) as session:
        scan = ScanRepository(session).get(finished.scan_id)
        assert scan is not None
        assert scan.status == "completed"
        assert scan.total_files == 2


def test_classify_job_completes_after_scan(engine: Engine, tmp_path: Path) -> None:
    source = tmp_path / "source"
    _copy_fixtures(source, ("iphone_jpeg_gps.jpg",))

    with Session(engine) as session:
        scan_job = submit_scan_job(session, str(source), True)
        scan_job_id = scan_job.id
    assert scan_job_id is not None
    scan_result = _wait_for_terminal(engine, scan_job_id)
    assert scan_result.scan_id is not None

    with Session(engine) as session:
        classify_job = submit_classify_job(session, scan_result.scan_id)
        classify_job_id = classify_job.id
    assert classify_job_id is not None

    finished = _wait_for_terminal(engine, classify_job_id)
    assert finished.status == "completed"
    assert finished.processed >= 1


def test_cancellation_stops_classify_before_any_file(engine: Engine, tmp_path: Path) -> None:
    """classify_scan checks should_cancel before each file, so a cancel
    requested before the job starts processing stops it at zero files —
    deterministic regardless of how many files exist.
    """
    source = tmp_path / "source"
    _copy_fixtures(source, ("iphone_jpeg_gps.jpg", "sample_video.mp4"))

    with Session(engine) as session:
        scan_job = submit_scan_job(session, str(source), True)
        scan_job_id = scan_job.id
    assert scan_job_id is not None
    scan_result = _wait_for_terminal(engine, scan_job_id)
    assert scan_result.scan_id is not None

    original_run = job_runner_module._run_classify_job

    def _cancel_then_run(engine: Engine, job_id: int, params: dict[str, object]) -> None:
        with Session(engine) as session:
            job = JobRepository(session).get(job_id)
            assert job is not None
            job.cancel_requested = True
            JobRepository(session).update(job)
        original_run(engine, job_id, params)

    job_runner_module._run_classify_job = _cancel_then_run
    try:
        with Session(engine) as session:
            classify_job = submit_classify_job(session, scan_result.scan_id)
            classify_job_id = classify_job.id
        assert classify_job_id is not None

        finished = _wait_for_terminal(engine, classify_job_id)
    finally:
        job_runner_module._run_classify_job = original_run

    assert finished.status == "cancelled"
    assert finished.processed == 0


def test_job_failure_marks_status_failed(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(job_runner_module, "scan_folder", _raise)

    with Session(engine) as session:
        job = submit_scan_job(session, str(tmp_path), True)
        job_id = job.id
    assert job_id is not None

    finished = _wait_for_terminal(engine, job_id)

    assert finished.status == "failed"
    assert finished.error_code == "JOB_FAILED"
    assert finished.error_message is not None and "boom" in finished.error_message
