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
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session

from backend.app.core.tools import ToolNotAvailableError, require_tools
from backend.app.models.job import Job
from backend.app.models.move_plan import MoveOperation
from backend.app.models.scan import Scan
from backend.app.repositories.job_repository import JobRepository
from backend.app.repositories.media_file_repository import MediaFileRepository
from backend.app.repositories.move_operation_repository import MoveOperationRepository
from backend.app.repositories.scan_repository import ScanRepository
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
_PROGRESS_WRITE_INTERVAL_SECONDS = 0.25


class _ProgressWriter:
    """Coalesce rapid per-file updates to avoid a second SQLite write per file."""

    def __init__(self, engine: Engine, job_id: int) -> None:
        self._engine = engine
        self._job_id = job_id
        self._last_write: float | None = None
        self._pending: dict[str, object] = {}

    def update(self, **fields: object) -> None:
        self._pending.update(fields)
        now = time.monotonic()
        if self._last_write is None or now - self._last_write >= _PROGRESS_WRITE_INTERVAL_SECONDS:
            self.flush()

    def flush(self) -> None:
        if not self._pending:
            return
        _update_job(self._engine, self._job_id, **self._pending)
        self._pending.clear()
        self._last_write = time.monotonic()


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


def _mark_linked_scan_failed(engine: Engine, job_id: int) -> None:
    """Keep a partially built scan from being treated as classifiable."""
    with Session(engine) as session:
        job = JobRepository(session).get(job_id)
        if job is None or job.job_type != "scan" or job.scan_id is None:
            return
        _set_scan_status(session, job.scan_id, "failed")


def _set_scan_status(session: Session, scan_id: int, status: str) -> None:
    scan_repository = ScanRepository(session)
    scan = scan_repository.get(scan_id)
    if scan is None:
        return
    scan.status = status
    scan.finished_at = datetime.now(UTC)
    scan_repository.update(scan)


def _run_scan_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    _update_job(
        engine,
        job_id,
        status="running",
        message="checking local tools",
        started_at=datetime.now(UTC),
    )
    require_tools("exiftool", "ffprobe")
    progress = _ProgressWriter(engine, job_id)

    def on_scan_created(scan: Scan) -> None:
        _update_job(engine, job_id, scan_id=scan.id)

    def on_scan_progress(progress: ScanProgress) -> None:
        _update_job(engine, job_id, processed=progress.processed_files, message="scanning")

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
        progress.flush()
        _update_job(engine, job_id, total=scan.total_files, processed=scan.processed_files)

        if scan.status == "cancelled":
            _update_job(
                engine,
                job_id,
                status="cancelled",
                scan_id=scan_id,
                message=None,
                finished_at=datetime.now(UTC),
            )
            return

        detect_media_types_for_scan(
            session,
            scan_id,
            on_progress=lambda n: progress.update(message=f"detecting ({n})"),
            should_cancel=lambda: _should_cancel(engine, job_id),
        )
        progress.flush()
        if _should_cancel(engine, job_id):
            _set_scan_status(session, scan_id, "cancelled")
            _update_job(
                engine,
                job_id,
                status="cancelled",
                scan_id=scan_id,
                message=None,
                finished_at=datetime.now(UTC),
            )
            return

        extract_metadata_for_scan(
            session,
            scan_id,
            on_progress=lambda n: progress.update(message=f"extracting ({n})"),
            should_cancel=lambda: _should_cancel(engine, job_id),
        )
        progress.flush()

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    if final_status == "cancelled":
        with Session(engine) as session:
            _set_scan_status(session, scan_id, "cancelled")
    _update_job(
        engine,
        job_id,
        status=final_status,
        scan_id=scan_id,
        message=None,
        finished_at=datetime.now(UTC),
    )


def _run_classify_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    scan_id = int(str(params["scan_id"]))
    with Session(engine) as session:
        total = sum(
            row.media_kind in ("image", "video")
            for row in MediaFileRepository(session).list_by_scan(scan_id)
        )
    _update_job(
        engine,
        job_id,
        status="running",
        scan_id=scan_id,
        total=total,
        started_at=datetime.now(UTC),
    )

    processed_count = 0
    progress = _ProgressWriter(engine, job_id)

    def _on_progress(_media: object, _result: object) -> None:
        nonlocal processed_count
        processed_count += 1
        progress.update(processed=processed_count)

    with Session(engine) as session:
        classify_scan(
            session,
            scan_id,
            on_progress=_on_progress,
            should_cancel=lambda: _should_cancel(engine, job_id),
        )
    progress.flush()

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    _update_job(
        engine,
        job_id,
        status=final_status,
        processed=processed_count,
        message=None,
        finished_at=datetime.now(UTC),
    )


def _run_execute_job(engine: Engine, job_id: int, params: dict[str, object]) -> None:
    move_plan_id = int(str(params["move_plan_id"]))
    with Session(engine) as session:
        operations = MoveOperationRepository(session).list_by_plan(move_plan_id)
        total = sum(operation.status != "blocked" for operation in operations)
        processed_count = sum(
            operation.status in ("completed", "failed", "skipped", "cancelled")
            for operation in operations
        )
    _update_job(
        engine,
        job_id,
        status="running",
        move_plan_id=move_plan_id,
        total=total,
        processed=processed_count,
        started_at=datetime.now(UTC),
    )

    progress = _ProgressWriter(engine, job_id)

    def _on_progress(_operation: MoveOperation) -> None:
        nonlocal processed_count
        processed_count += 1
        progress.update(processed=processed_count)

    with Session(engine) as session:
        execute_move_plan(
            session,
            move_plan_id,
            on_progress=_on_progress,
            should_cancel=lambda: _should_cancel(engine, job_id),
        )
        processed_count = sum(
            operation.status in ("completed", "failed", "skipped", "cancelled")
            for operation in MoveOperationRepository(session).list_by_plan(move_plan_id)
        )
    progress.flush()

    final_status = "cancelled" if _should_cancel(engine, job_id) else "completed"
    _update_job(
        engine,
        job_id,
        status=final_status,
        processed=processed_count,
        message=None,
        finished_at=datetime.now(UTC),
    )


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
        except ToolNotAvailableError as error:
            _mark_linked_scan_failed(engine, job_id)
            _update_job(
                engine,
                job_id,
                status="failed",
                error_code="TOOL_NOT_AVAILABLE",
                error_message=str(error),
                message=None,
                finished_at=datetime.now(UTC),
            )
        except Exception as error:  # noqa: BLE001 - a job must never crash the worker thread
            _mark_linked_scan_failed(engine, job_id)
            _update_job(
                engine,
                job_id,
                status="failed",
                error_code="JOB_FAILED",
                error_message=str(error),
                message=None,
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
