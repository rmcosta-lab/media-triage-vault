# Plan — Phase 16: Execute/resume CLI + move report

## 1. Move report service

- New `backend/app/services/move_report.py`:
  - `MoveReportSummary` frozen dataclass: `total_operations`,
    `total_planned`, `total_completed`, `total_failed`, `total_skipped`,
    `total_blocked`, `total_bytes_moved`, `elapsed_seconds`.
  - `_operation_row(operation) -> dict[str, object]`: flattens one
    `MoveOperation` (all README §18 fields plus
    `planned_destination_path`) into JSON/CSV-safe primitives
    (`datetime` → `isoformat()`).
  - `generate_move_report(session, move_plan_id, output_dir,
    execution_summary: MoveExecutionSummary, elapsed_seconds: float) ->
    MoveReportSummary`: load the `MovePlan` (raise `ValueError` if
    missing) and every `MoveOperation` via
    `MoveOperationRepository.list_by_plan`; write `move_report.json`
    (plan id/scan id/collision policy/validation mode, `totals` block,
    `by_error_code`, full `operations` array) and `move_report.csv` (one
    row per operation, empty-plan-safe header); return the summary.

## 2. Executor test addition (Phase 15 module)

- `backend/tests/unit/test_move_executor.py`: add
  `test_should_cancel_stops_before_next_operation` — two `planned`
  operations, `should_cancel` returns `True` after the first call;
  assert the first operation reaches `completed` and the second is still
  `planned` untouched.

## 3. CLI wiring

- `backend/app/cli/main.py`:
  - Imports: `signal`, `time`, `types.FrameType`, `MovePlanRepository`,
    `MoveOperationRepository`, `execute_move_plan`, `TERMINAL_STATUSES`
    (from `services.move_executor`), `generate_move_report`.
  - `@app.command("execute")` —
    `execute_command(scan_id: int = typer.Option(..., "--scan-id"),
    output: Path = typer.Option(..., "--output"), confirm: bool =
    typer.Option(False, "--confirm"), validation_mode: str | None =
    typer.Option(None, "--validation-mode"), database: Path | None =
    typer.Option(None, "--database", hidden=True))`:
    1. Resolve `MovePlanRepository.get_latest_for_scan(scan_id)`; exit 1
       with a message if `None`.
    2. Load operations via `MoveOperationRepository.list_by_plan`; split
       into `planned`/`blocked`/already-`TERMINAL_STATUSES`; print the
       Etapa 6 summary (count + bytes to move, blocked count, already-
       finished count).
    3. If not `confirm`: print "Nothing executed. Re-run with --confirm
       to execute." and `raise typer.Exit(code=0)`.
    4. Install a `SIGINT` handler that sets a `cancel_requested` flag
       and prints a notice instead of raising; restore the previous
       handler in a `finally` block.
    5. Time the call with `time.monotonic()`; run `execute_move_plan`
       with `on_progress=_report_execute_progress`,
       `should_cancel=lambda: cancel_requested`.
    6. `output.mkdir(parents=True, exist_ok=True)`; call
       `generate_move_report`.
    7. Print the final summary line and the report file paths.
  - `_report_execute_progress(operation: MoveOperation) -> None`: prints
    `source -> planned_destination: status` with the `error_code` in
    parentheses when `status == "failed"`.

## 4. Tests

- `backend/tests/unit/test_move_report.py`: build a small plan +
  operations directly (mirroring `test_move_executor.py`'s fixtures) in
  a mix of `completed`/`failed`/`blocked`/`planned` states; call
  `generate_move_report`; assert `move_report.json` parses and its
  `totals` match, `move_report.csv` has one data row per operation with
  the right header, and a missing `move_plan_id` raises `ValueError`.
- `backend/tests/integration/test_execute_cli.py`:
  - Full pipeline test: `scan → classify → destinations → plan →
    execute --confirm` over `backend/tests/fixtures/` (temp copy) into a
    temp destination root. Assert: exit codes `0`; every non-blocked
    `MoveOperation` reaches `completed`; every destination file exists
    with the same content (hash) as the original fixture; source files
    for completed operations no longer exist; `move_report.json`/`.csv`
    exist under `--output` and their totals match the CLI's printed
    summary.
  - `execute` without `--confirm`: exit code `0`, prints the summary,
    and no `MoveOperation` status changes (still `planned`) — asserted
    by reading the DB after the call, and no file appears under the
    destination root.
  - `execute` with no move plan for the scan: exit code `1`.
  - **Kill-and-resume**: after `plan`, call `execute_move_plan` directly
    (not through the CLI) with `should_cancel` forced `True` after the
    first operation, simulating an interrupted run — assert a mix of
    `completed` and still-`planned` rows. Then invoke the `execute`
    CLI command with `--confirm` again: assert exit code `0`, every
    remaining `planned` row reaches `completed`, and the previously
    `completed` row is untouched (same `finished_at`).

## 5. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer execute --help` runs cleanly.
- Manual: run the full `scan → classify → destinations → plan → execute`
  pipeline against `backend/tests/fixtures/` with a temp destination
  root; confirm files actually move, `move_report.json`/`.csv` are
  produced, and pressing Ctrl+C during a real (larger, if needed) run
  stops between files rather than mid-copy.
