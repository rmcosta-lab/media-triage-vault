# Validation — Phase 18: Jobs + progress

### Functional

- [x] `POST /api/scans` queues a scan job and returns immediately (202)
      — `test_post_scans_queues_and_completes`, manual `curl` (job
      returned `status="queued"` instantly, scan completed
      asynchronously).
- [x] `POST /api/scans/{scan_id}/classify` queues a classify job —
      `test_post_classify_happy_path`, manual `curl`.
- [x] `POST /api/scans/{scan_id}/cancel` requests cancellation of the
      active job — `cancel_scan_job` sets `cancel_requested=True`;
      404-when-none-active covered by
      `test_cancel_with_no_active_job_returns_404` and manual `curl`.
- [x] `GET /api/jobs/{job_id}` reports current status/progress —
      exercised throughout via polling in every job test.
- [x] `GET /api/jobs/{job_id}/events` streams live progress via SSE
      until a terminal state — `test_job_events_stream_reaches_terminal_state`,
      manual `curl -N` (received a `completed` event).
- [x] A cancelled job stops between files/batches, never mid-file —
      `test_scan_folder_honors_should_cancel_between_batches` (Phase 4
      module), `test_cancellation_stops_classify_before_any_file`.
- [x] The HTTP server never blocks while a job runs — the job runs on a
      separate daemon thread; every job test's `POST` returns before the
      job reaches a terminal state, and `GET`s are polled concurrently
      while it's still `running`.

### Roadmap done criterion

- [x] A scan runs via the API with live progress observable end to end
      — `test_jobs_api_integration.py`'s full launch→watch→classify→
      watch→read-back flow, and a manual `media-organizer serve` run
      with `curl -N .../jobs/1/events` streaming to `completed`.

### Tests

- [x] Job runner covered directly: scan job completes
      (`test_scan_job_completes_and_stamps_scan_id`), classify job
      completes (`test_classify_job_completes_after_scan`),
      cancellation stops a job early
      (`test_cancellation_stops_classify_before_any_file`), an exception
      inside a job marks it `failed` without crashing the worker thread
      (`test_job_failure_marks_status_failed`) —
      `test_job_runner.py`, 4 tests.
- [x] API routes covered: `POST /scans` happy path + invalid path,
      `POST .../classify` happy path + missing scan, `POST .../cancel`
      with no active job, `GET /jobs/{id}` happy path + missing,
      `GET /jobs/{id}/events` happy path (consumed to a terminal event)
      + missing job — `test_job_routes.py`, 8 tests.
- [x] Integration test: full launch-scan → watch → classify → watch →
      read-back flow over fixtures through the API only —
      `test_jobs_api_integration.py`, 1 test.
- [x] `scan_folder`'s `should_cancel` mechanism itself unit-tested at
      the batch boundary — `test_scan_folder_honors_should_cancel_between_batches`
      (added to Phase 4's `test_scanner.py`).

### Safety

- [x] No network call is made anywhere in this phase's code — confirmed
      by reading `job_runner.py`/`routes.py` imports (stdlib `queue`/
      `threading`/`asyncio`/`json`, SQLModel, FastAPI/Starlette, and
      already-audited service/repository code only).
- [x] Cancellation is honored only between files/batches — confirmed by
      reading every `should_cancel` call site: `scan_folder` (after a
      batch `flush()`), `detect_media_types_for_scan` (before each row),
      `extract_metadata_for_scan` (before each batch),
      `classify_scan` (before each file) — none sit inside a single
      file's read/write.
- [x] The job worker never writes to a scanned source file — unchanged
      from the underlying Phase 4/5/6/12 services, which remain
      read-only toward the source tree.
- [x] A failing job never crashes the worker thread or leaves it stuck
      — `_worker_loop`'s `except Exception` + `finally: task_done()`,
      verified by `test_job_failure_marks_status_failed` (the worker
      thread keeps working after a failure — implicitly proven since
      later tests in the same process still submit and complete jobs).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean — "Success: no issues found in 101
      source files".
- [x] `uv run pytest` green — 274 passed (14 new: 4 job-runner unit,
      1 scanner cancellation unit, 8 job-route unit, 1 jobs-API
      integration).

### Manual

- [x] `media-organizer serve` running: `POST /api/scans` against a real
      2-file fixture copy returned `202`/`status=queued` immediately;
      `GET /api/jobs/1/events` streamed to a `completed` event
      (`scan_id=1`, `processed=2`); `GET /api/scans/1` confirmed
      `total_files=2`; `POST /api/scans/1/classify` completed
      (`processed=2`); `POST /api/scans/999/cancel` → 404; `/docs` still
      404. Confirmed via `netstat` the process only listened on
      `127.0.0.1`. Runtime database temporarily swapped for the manual
      run and restored afterward.
