"""Background job runner — README §26, roadmap Phases 18-19.

A single daemon worker thread drains a local `queue.Queue`, running one
job at a time (`limitar concorrência de leitura`) and persisting every
bit of state in the `Job` SQLite row rather than in memory — the row is
the source of truth `GET /api/jobs/{job_id}` and the SSE stream both
read from. No Celery/Redis (README §26). `should_cancel` is checked
between files/batches only, via the underlying services' own hooks
(Phase 4/6/12/15) — a job is never interrupted mid-file.
"""

from __future__ import annotations

import json
import queue
import threading
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.models.job import Job
from backend.app.models.move_plan import MoveOperation
from backend.app.models.scan import Scan
from backend.app.repositories.job_repository import JobRepository
from backend.app.services.classification import classify_scan
from backend.app.services.media_type import detect_media_types_for_scan
from backend.app.services.metadata import extract_metadata_for_scan
from backend.app.services.move_executor import execute_move_plan
from backend.app.services.scanner import ScanProgress, scan_folder

# Each queued item carries its own engine — the one bound to whichever
# session `submit_scan_job`/`submit_classify_job` was called with — so the
# worker thread always talks to the same database the API request did
# (tests override the session dependency to point at a temp database;
# there is otherwise a single real engine in production).
_job_queue: queue.Queue[tuple[Engine, int]] = queue.Queue()
_worker_lock = threading.Lock()
_worker_started = False


def _should_cancel(engine: Engine, job_id: int) -> bool:
    with Session(engine) as session:
        job = JobRepository(session).get(job_id)
        return job is not None and job.cancel_requested


def _update_job(engine: Engine, job_id: int, **fields: object) -> None:
    with Session(engine) as session:
        repository = JobRepository(session)
        job = repository.get(job_id)
        if job is None:
            return
        for name, value in fields.items():
            setattr(job, name, value)
        repository.update(job)


def _run_scan_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    _update_job(engine, job_id, status="running", started_at=datetime.now(UTC))

    def on_scan_created(scan: Scan) -> None:
        _update_job(engine, job_id, scan_id=scan.id)

    def on_scan_progress(progress: ScanProgress) -> None:
        _update_job(engine, job_id, processed=progress.processed_files)

    with Session(engine) as session:
        scan = scan_folder(
            session,
            Path(str(params["source_root"])),
            recursive=bool(params.get("recursive", True)),
            on_progress=on_scan_progress,
            should_cancel=lambda: _should_cancel(engine, job_id),
            on_scan_created=on_scan_created,
        )
        assert scan.id is not None
        scan_id = scan.id

        if scan.status == "cancelled":
            _update_job(
                engine, job_id, status="cancelled", scan_id=scan_id, finished_at=datetime.now(UTC)
            )
            return

        detect_media_types_for_scan(
            session,
            scan_id,
            on_progress=lambda n: _update_job(engine, job_id, message=f"detecting ({n})"),
            should_cancel=lambda: _should_cancel(engine, job_id),
        )
        if _should_cancel(engine, job_id):
            _update_job(
                engine, job_id, status="cancelled", scan_id=scan_id, finished_at=datetime.now(UTC)
            )
            return

        extract_metadata_for_scan(
            session,
            scan_id,
            on_progress=lambda n: _update_job(engine, job_id, message=f"extracting ({n})"),
            should_cancel=lambda: _should_cancel(engine, job_id),
        )

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    _update_job(engine, job_id, status=final_status, scan_id=scan_id, finished_at=datetime.now(UTC))


def _run_classify_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    scan_id = int(str(params["scan_id"]))
    _update_job(engine, job_id, status="running", scan_id=scan_id, started_at=datetime.now(UTC))

    processed_count = 0

    def _on_progress(_media: object, _result: object) -> None:
        nonlocal processed_count
        processed_count += 1
        _update_job(engine, job_id, processed=processed_count)

    with Session(engine) as session:
        classify_scan(
            session,
            scan_id,
            on_progress=_on_progress,
            should_cancel=lambda: _should_cancel(engine, job_id),
        )

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    _update_job(engine, job_id, status=final_status, finished_at=datetime.now(UTC))


def _run_execute_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    move_plan_id = int(str(params["move_plan_id"]))
    _update_job(
        engine, job_id, status="running", move_plan_id=move_plan_id, started_at=datetime.now(UTC)
    )

    processed_count = 0

    def _on_progress(_operation: MoveOperation) -> None:
        nonlocal processed_count
        processed_count += 1
        _update_job(engine, job_id, processed=processed_count)

    with Session(engine) as session:
        execute_move_plan(
            session,
            move_plan_id,
            on_progress=_on_progress,
            should_cancel=lambda: _should_cancel(engine, job_id),
        )

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    _update_job(engine, job_id, status=final_status, finished_at=datetime.now(UTC))


def _worker_loop() -> None:
    while True:
        engine, job_id = _job_queue.get()
        try:
            with Session(engine) as session:
                job = JobRepository(session).get(job_id)
                if job is None:
                    continue
                job_type = job.job_type
                params: dict[str, object] = json.loads(job.params_json)

            if job_type == "scan":
                _run_scan_job(engine, job_id, params)
            elif job_type == "classify":
                _run_classify_job(engine, job_id, params)
            elif job_type == "execute":
                _run_execute_job(engine, job_id, params)
        except Exception as error:  # noqa: BLE001 - a job must never crash the worker thread
            _update_job(
                engine,
                job_id,
                status="failed",
                error_code="JOB_FAILED",
                error_message=str(error),
                finished_at=datetime.now(UTC),
            )
        finally:
            _job_queue.task_done()


def _ensure_worker_started() -> None:
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            threading.Thread(target=_worker_loop, daemon=True, name="job-worker").start()
            _worker_started = True


def _engine_of(session: Session) -> Engine:
    engine = session.get_bind()
    assert isinstance(engine, Engine)
    return engine


def submit_scan_job(session: Session, source_root: str, recursive: bool) -> Job:
    """Queue a scan job. The resulting `Scan` row's id lands on `Job.scan_id` once created."""
    job = JobRepository(session).create(
        Job(
            job_type="scan",
            status="queued",
            params_json=json.dumps({"source_root": source_root, "recursive": recursive}),
        )
    )
    assert job.id is not None
    _ensure_worker_started()
    _job_queue.put((_engine_of(session), job.id))
    return job


def submit_classify_job(session: Session, scan_id: int) -> Job:
    """Queue a classify job against an existing scan."""
    job = JobRepository(session).create(
        Job(
            job_type="classify",
            scan_id=scan_id,
            status="queued",
            params_json=json.dumps({"scan_id": scan_id}),
        )
    )
    assert job.id is not None
    _ensure_worker_started()
    _job_queue.put((_engine_of(session), job.id))
    return job


def submit_execute_job(session: Session, move_plan_id: int) -> Job:
    """Queue an execute job for an approved move plan. `Job.id` is the "move run" id."""
    job = JobRepository(session).create(
        Job(
            job_type="execute",
            move_plan_id=move_plan_id,
            status="queued",
            params_json=json.dumps({"move_plan_id": move_plan_id}),
        )
    )
    assert job.id is not None
    _ensure_worker_started()
    _job_queue.put((_engine_of(session), job.id))
    return job
