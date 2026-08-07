# Plan — Phase 19: Plan/execute API

## 1. Report builders become pure functions of persisted state

- `backend/app/services/move_report.py`: replace the `execution_summary:
  MoveExecutionSummary` parameter with computation directly from the
  `MoveOperation` rows (`total_completed`/`failed`/`skipped`/`blocked`/
  `still_planned`/`bytes_moved`/`by_error_code`, all derived from
  `operation.status`/`error_code`/`destination_size`). New
  `build_move_report_payload(session, move_plan_id, elapsed_seconds) ->
  dict`; `generate_move_report(session, move_plan_id, output_dir,
  elapsed_seconds) -> MoveReportSummary` becomes a thin wrapper that
  calls it and writes `move_report.json`/`.csv`.
- `backend/app/cli/main.py`'s `execute_command`: drop the now-unused
  `execution_summary` local (still calls `execute_move_plan` for its
  side effects), update the `generate_move_report` call site to the new
  signature.
- `backend/app/services/reports.py`: extract `_report_payload(scan,
  rows, summary, generated_at) -> dict` from `_write_report_json` (same
  dict, now reused); new `build_report_payload(session, scan_id) ->
  dict` — loads the scan's `MediaFile` rows, calls the existing
  `_build_rows`/`_summarize` with an empty `thumbnail_results` dict (no
  thumbnails generated for this on-demand read), returns the payload
  with `generated_at=datetime.now(UTC)`.
- Update `backend/tests/unit/test_move_report.py` for the new
  `generate_move_report` signature.

## 2. Job model + runner extended for "execute"

- `backend/app/models/job.py`: add `move_plan_id: int | None = None`;
  `JOB_TYPES` gains `"execute"`.
- `backend/app/services/job_runner.py`: `_run_execute_job(engine,
  job_id, params)` — marks `running` with `move_plan_id` stamped
  immediately (known up front, unlike a scan job's `scan_id`); calls
  `execute_move_plan` with `on_progress` incrementing `Job.processed`
  per operation and `should_cancel` wired the same way as every other
  job type; final status `completed`/`cancelled`. `_worker_loop` gains
  the `"execute"` dispatch branch. `submit_execute_job(session,
  move_plan_id) -> Job`.

## 3. API schemas

- `backend/app/api/schemas.py`: `DestinationConfigRequest`,
  `DestinationRuleRead`, `MovePlanCreateRequest`, `MoveOperationRead`,
  `MovePlanRead` (header + `total_planned`/`total_blocked`/
  `total_bytes_planned`/`by_error_code` + `operations: list[
  MoveOperationRead]`); `JobRead` gains `move_plan_id`.

## 4. API routes

- `backend/app/api/routes.py`:
  - `_build_move_plan_read(session, move_plan) -> MovePlanRead` — shared
    by every route that returns a plan.
  - `PUT /scans/{scan_id}/destinations` — `404` missing scan; calls
    `set_destination_rules`, `400` on `ValueError` (unknown routing
    group); returns `list[DestinationRuleRead]`.
  - `POST /scans/{scan_id}/move-plan` — `404` missing scan; calls
    `generate_move_plan`, `400` on `ValueError` (unsupported
    `collision_policy`); returns the freshly generated plan via
    `MovePlanRepository.get_latest_for_scan` + `_build_move_plan_read`.
  - `GET /move-plans/{plan_id}` — `404` or `_build_move_plan_read`.
  - `POST /move-plans/{plan_id}/approve` — `404` or stamps
    `approved_at = datetime.now(UTC)`, returns the plan.
  - `POST /move-plans/{plan_id}/execute` — `404` missing plan; `400` if
    `approved_at is None`; `submit_execute_job`; `202` + `JobRead`.
  - `_get_execute_job_or_404(session, run_id) -> Job` — shared helper,
    `404` unless a `Job` with that id exists and `job_type == "execute"`.
  - `GET /move-runs/{run_id}` — `JobRead` via the helper.
  - `POST /move-runs/{run_id}/cancel` — sets `cancel_requested=True`.
  - `GET /move-runs/{run_id}/report` — elapsed seconds from
    `Job.started_at`/`finished_at` (`0.0` if either is missing); `dict`
    via `build_move_report_payload`.
  - `GET /scans/{scan_id}/report` — `dict` via `build_report_payload`,
    `404` on `ValueError`.

## 5. Tests

- `backend/tests/unit/test_plan_execute_routes.py` (`TestClient`,
  dependency overrides matching the Phase 17/18 pattern; a real scanned
  + classified fixture set built via `submit_scan_job`/
  `submit_classify_job` and polled to completion, then the
  destinations/move-plan/execute flow driven purely over HTTP):
  - `PUT .../destinations` happy path + unknown routing group (`400`) +
    missing scan (`404`).
  - `POST .../move-plan` happy path (asserts `total_planned` and at
    least one `MoveOperationRead`) + missing scan (`404`).
  - `GET /move-plans/{id}` happy path + missing (`404`).
  - `POST /move-plans/{id}/approve` sets `approved_at`.
  - `POST /move-plans/{id}/execute` before approval → `400`; after
    approval → `202`, poll `GET /move-runs/{id}` to a terminal state,
    assert `completed` and the destination file exists with the source
    fixture's hash.
  - `GET /move-runs/{id}` and `.../cancel` for a non-existent/non-execute
    id → `404`.
  - `GET /move-runs/{id}/report` after completion: `totals.completed`
    matches, `operations` has one row per planned/blocked file.
  - `GET /scans/{id}/report`: `total_files` matches, no
    coordinate-shaped key anywhere in the payload.
- `backend/tests/integration/test_plan_execute_api_integration.py`: the
  full scan → classify → destinations → move-plan → approve → execute →
  report flow over `backend/tests/fixtures/`, entirely through the API,
  asserting the destination tree matches the source fixtures by hash and
  the source files are gone.

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- Manual: `media-organizer serve`, drive the full flow with `curl`
  against a fixture copy, confirming files actually move and the two
  report endpoints return sane JSON.
