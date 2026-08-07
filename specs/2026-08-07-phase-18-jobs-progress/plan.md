# Plan — Phase 18: Jobs + progress

## 1. Cancellation hooks on existing services

- `backend/app/services/scanner.py`: `scan_folder` gains
  `should_cancel: Callable[[], bool] | None = None` (checked right after
  each batch `flush()`, setting `Scan.status = "cancelled"` instead of
  `"completed"` if triggered) and `on_scan_created: Callable[[Scan],
  None] | None = None` (fired immediately after the `Scan` row is
  created, before the file walk starts).
- `backend/app/services/media_type.py`: `detect_media_types_for_scan`
  gains `should_cancel`, checked once per row before processing it.
- `backend/app/services/metadata.py`: `extract_metadata_for_scan` gains
  `should_cancel`, checked once per batch before dispatching it to
  ExifTool.
- `backend/app/services/classification.py`: `classify_scan` gains
  `should_cancel`, checked once per file before classifying it.
- All four default to `None` — no existing CLI call site changes
  behavior.

## 2. Job model + repository

- New `backend/app/models/job.py`: `Job(SQLModel, table=True)` per
  requirements.md's field list; `JOB_TYPES`, `JOB_STATUSES` tuples.
- `backend/app/models/__init__.py`: add `Job`.
- New `backend/app/repositories/job_repository.py`:
  `JobRepository(Repository[Job])` + `list_active_for_scan(scan_id) ->
  Sequence[Job]` (status in `queued`/`running`).

## 3. Job runner service

- New `backend/app/services/job_runner.py`:
  - `_job_queue: queue.Queue[tuple[Engine, int]]`, `_worker_lock`,
    `_worker_started` module state.
  - `_should_cancel(engine, job_id) -> bool`, `_update_job(engine,
    job_id, **fields) -> None` — both open a short-lived `Session` on
    the passed engine.
  - `_run_scan_job(engine, job_id, params)`: marks `running`; runs
    `scan_folder` → (if not cancelled) `detect_media_types_for_scan` →
    (if not cancelled) `extract_metadata_for_scan`, all against one
    `Session`; wires `on_scan_created` to stamp `Job.scan_id` early and
    each stage's `on_progress`/`should_cancel` to `_update_job`/
    `_should_cancel`; sets the final `status`
    (`completed`/`cancelled`).
  - `_run_classify_job(engine, job_id, params)`: marks `running`; runs
    `classify_scan` with `on_progress` incrementing `Job.processed` and
    `should_cancel` wired the same way; sets the final status.
  - `_worker_loop()`: `while True: engine, job_id = _job_queue.get()`;
    dispatch by `Job.job_type`; any uncaught exception is caught and
    turned into `status="failed"` (a job must never crash the worker
    thread); `task_done()` in `finally`.
  - `_ensure_worker_started()`: lazily starts the one daemon thread.
  - `submit_scan_job(session, source_root, recursive) -> Job` /
    `submit_classify_job(session, scan_id) -> Job`: create the `Job` row
    (status `queued`), capture `session.get_bind()`, enqueue
    `(engine, job.id)`, return the row.

## 4. API wiring

- `backend/app/api/schemas.py`: `ScanCreateRequest` (`source_root`,
  `recursive`), `JobRead`.
- `backend/app/api/routes.py`:
  - `POST /scans` — validate `source_root` is an existing directory
    (`400` otherwise), `submit_scan_job`, `202` + `JobRead`.
  - `POST /scans/{scan_id}/classify` — `404` if the scan doesn't exist,
    else `submit_classify_job`, `202` + `JobRead`.
  - `POST /scans/{scan_id}/cancel` — `404` if no active job for
    `scan_id`, else set `cancel_requested=True` and return the job.
  - `GET /jobs/{job_id}` — `404` or `JobRead`.
  - `GET /jobs/{job_id}/events` — `404` upfront if the job doesn't
    exist; otherwise an `async def` `StreamingResponse` polling the
    same engine (`session.get_bind()`) every 0.3s, yielding `data:
    <JobRead JSON>\n\n` only when the payload changes, stopping once
    `status` is terminal.

## 5. Tests

- `backend/tests/unit/test_job_runner.py`: temp SQLite engine, no HTTP.
  - `submit_scan_job` against a small fixture directory completes with
    `status="completed"`, `Job.scan_id` set, `Scan.total_files` matching
    the fixture count (poll `Job`/`Scan` rows directly with a short
    retry loop since the worker runs asynchronously).
  - `submit_classify_job` against an already-scanned+detected+
    extracted fixture set completes and produces `Classification` rows.
  - Cancellation: `submit_scan_job` against a large-enough synthetic
    tree (many small files, batch size lowered via monkeypatch) then
    immediately set `cancel_requested=True`; assert the job ends
    `status="cancelled"` with `processed < total possible` and the scan
    row itself `status="cancelled"`.
  - A job whose `job_type` service raises is marked `status="failed"`
    with `error_code="JOB_FAILED"` (monkeypatch `scan_folder` to raise).
- `backend/tests/unit/test_job_routes.py` (`TestClient`, dependency
  overrides matching `test_api_routes.py`'s pattern):
  - `POST /api/scans` with a real temp fixture directory → `202`,
    `JobRead` with `status` in (`queued`, `running`); poll `GET
    /api/jobs/{id}` until terminal, assert `completed` and `scan_id`
    populated; `GET /api/scans/{scan_id}` then serves the result.
  - `POST /api/scans` with a non-existent `source_root` → `400`.
  - `POST /api/scans/{scan_id}/classify` on an unknown scan → `404`; on
    a real scanned+detected fixture set → `202`, poll to `completed`,
    `GET /api/files/{id}/classification` then serves a result.
  - `POST /api/scans/{scan_id}/cancel` with no active job → `404`.
  - `GET /api/jobs/{job_id}/events` for an unknown job → `404`; for a
    real job, consume the SSE stream (`httpx` stream iteration) and
    assert the last event's `status` is terminal.
- `backend/tests/integration/test_jobs_api_integration.py`: `POST
  /api/scans` against `backend/tests/fixtures/`, poll to completion,
  `POST .../classify`, poll to completion, then read the results back
  through Phase 17's `GET` routes — the full "launch and watch" flow
  Phase 18's done criterion describes.

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- Manual: `media-organizer serve`, `curl -X POST .../scans` against a
  fixture copy, then `curl -N .../jobs/{id}/events` and watch it stream
  to completion.
