# Validation — Phase 19: Plan/execute API

### Functional

- [x] `PUT /api/scans/{scan_id}/destinations` maps routing groups to
      folders — `test_put_destinations_happy_path`, manual `curl`.
- [x] `POST /api/scans/{scan_id}/move-plan` generates a dry-run plan —
      `test_move_plan_happy_path_and_missing_scan`, manual `curl`
      (2 planned, 0 blocked, `bytes_planned=1631`, nothing on disk yet).
- [x] `GET /api/move-plans/{plan_id}` serves the plan and its operations
      — exercised throughout; manual `curl` after execution shows both
      operations `completed`.
- [x] `POST /api/move-plans/{plan_id}/approve` records approval —
      `test_execute_requires_approval`, manual `curl`
      (`approved_at` populated).
- [x] `POST /api/move-plans/{plan_id}/execute` refuses an unapproved
      plan (`400`, confirmed manually) and queues an approved one
      (`202`).
- [x] `GET /api/move-runs/{run_id}` / `.../cancel` work against the
      execute job — `test_move_run_and_cancel_missing_return_404` +
      the happy path in `test_full_execute_flow_moves_a_real_file`.
- [x] `GET /api/move-runs/{run_id}/report` and
      `GET /api/scans/{scan_id}/report` serve correct JSON — both
      covered by tests and manual `curl` (move report:
      `completed=2, bytes_moved=1631`; scan report: joined
      file/classification data, correct `totals_by_group`).

### Roadmap done criterion

- [x] The full US-001→US-004 flow works over HTTP end to end —
      `test_plan_execute_api_integration.py` (6 fixtures, full flow,
      hash-verified) and a manual `curl` walkthrough against 2 real
      fixtures: scan → classify → destinations → move-plan → approve
      (blocked before) → execute → both reports, with both files
      verified moved on disk and the source directory left empty.

### Tests

- [x] Every new route covered: happy path and its error case(s) —
      `test_plan_execute_routes.py`, 10 tests.
- [x] `execute` before `approve` is rejected (`400`) —
      `test_execute_requires_approval`.
- [x] A full execute run reaches `completed` and moves a real fixture
      file, verified by content hash —
      `test_full_execute_flow_moves_a_real_file`,
      `test_plan_execute_api_integration.py`.
- [x] Both report endpoints exclude coordinate-shaped fields —
      `test_scan_report_excludes_coordinates`; move report never
      includes GPS fields by construction (`MoveOperation` has none).
- [x] Phase 16's `move_report.py` tests still pass after the signature
      refactor — `test_move_report.py`, updated and green.

### Safety

- [x] No network call is made anywhere in this phase's code — confirmed
      by reading every new/changed module's imports.
- [x] `execute` is unreachable without a prior `approve` — confirmed by
      reading `execute_move_plan_route` (the `400` check runs before
      `submit_execute_job` is ever called) and by the manual 400/202
      sequence above.
- [x] Report endpoints never write to disk — confirmed by reading
      `build_move_report_payload`/`build_report_payload` (no
      `Path.write`/`open(..., "w")` calls in either).
- [x] No coordinate-shaped key appears in either report payload —
      verified by test and by inspecting the manual `curl` output.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean — "Success: no issues found in 103
      source files".
- [x] `uv run pytest` green — 285 passed (11 new: 10 plan/execute-route
      unit, 1 full-flow integration).

### Manual

- [x] Full flow driven with `curl` against `media-organizer serve`:
      scan → classify → destinations → move-plan (dry run, nothing on
      disk) → execute-before-approve (`400`) → approve → execute (`202`)
      → move-run status (`completed`) → move-run report
      (`completed=2, bytes_moved=1631`) → scan report (joined data,
      correct group/country totals). Confirmed both files physically
      moved and the source directory ended up empty. Runtime database
      temporarily swapped for the manual run and restored afterward.
