# Validation — Phase 16: Execute/resume CLI + move report

### Functional (US-004 acceptance criteria)

- [x] Execution requires explicit confirmation — `execute` without
      `--confirm` performs no operation, verified by
      `test_execute_cli_without_confirm_does_nothing` and a manual run
      (printed "Nothing executed", no destination tree created).
- [x] Every operation is recorded — the journal (Phase 15) plus
      `move_report.json`/`.csv` — `test_generate_move_report_writes_json_and_csv`.
- [x] Nothing is silently overwritten — inherited from Phase 15,
      unchanged (`DESTINATION_EXISTS`).
- [x] Moved files are validated — inherited from Phase 15 (size/hash).
- [x] An interrupted run can be resumed — `test_kill_and_resume`.
- [x] Progress is shown per file during execution —
      `_report_execute_progress`, visible in the manual run output.
- [x] Failures are recorded with an error code/message — `by_error_code`
      in the move report, per-row `error_code`/`error_message` in
      `move_report.json`/`.csv`.
- [x] A final move report is generated — `move_report.json` +
      `move_report.csv`, confirmed by a manual run (8/8 completed,
      `bytes_moved=7012`).

### Roadmap done criterion

- [x] US-004 passes end to end via the CLI over fixtures — manual
      `scan → classify → destinations → plan → execute --confirm` run:
      8/8 files completed, source directory empty afterward, destination
      tree populated, `move_report.json`/`.csv` produced.
- [x] Kill-and-resume test: a partially-executed plan (`should_cancel`
      forced after the first file, simulating a kill), resumed via a
      second `execute --confirm` call, finishes every remaining file
      without redoing the already-completed one — `test_kill_and_resume`.

### Tests

- [x] `move_report.py` covered: JSON/CSV content and totals, missing
      plan raises `ValueError` — `test_move_report.py`, 2 tests.
- [x] `execute_move_plan`'s `should_cancel` stops the loop before the
      next `planned` operation —
      `test_should_cancel_stops_before_next_operation` (added to Phase
      15's `test_move_executor.py`).
- [x] Integration: full pipeline reaches `completed` for every mapped
      fixture, destination content matches source hash, sources of
      completed operations are gone — `test_execute_cli_end_to_end`.
- [x] Integration: no `--confirm` performs no execution —
      `test_execute_cli_without_confirm_does_nothing`.
- [x] Integration: missing move plan exits non-zero —
      `test_execute_cli_without_plan_exits_nonzero`.
- [x] Integration: kill-and-resume via the CLI — `test_kill_and_resume`.

### Safety

- [x] No network call is made — `move_report.py`/CLI `execute` command
      import only stdlib (`csv`, `json`, `signal`, `time`, `pathlib`),
      SQLModel, and already-audited service/repository code.
- [x] No file is overwritten — `DESTINATION_EXISTS` (Phase 15) still the
      only outcome for a conflicting destination; unchanged this phase.
- [x] `execute` never runs without `--confirm` — gated by an explicit
      `if not confirm: ... raise typer.Exit(code=0)` before
      `execute_move_plan` is ever called.
- [x] Cancellation (`SIGINT` handler) never fires mid-operation — the
      handler only sets a flag; `execute_move_plan`'s loop (Phase 15)
      only calls `should_cancel()` between operations, never during one.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean (via `ruff format .` — "1
      file reformatted, 87 files left unchanged" on the pass that
      produced the final state; re-run reports 0 changes needed).
- [x] `uv run mypy backend` clean — "Success: no issues found in 88
      source files".
- [x] `uv run pytest` green — 245 passed (7 new: 1 executor should_cancel,
      2 move-report unit, 4 execute-CLI integration).
- [x] `uv run media-organizer execute --help` runs without error —
      verified manually.

### Manual

- [x] Full pipeline manually run against `backend/tests/fixtures/`
      (8 files) with a temp destination root: all 8 completed, source
      directory ended up empty, `move_report.json`/`.csv` produced with
      correct totals (`bytes_moved=7012`).
- [ ] Ctrl+C during a real `execute --confirm` run stops between files,
      not mid-copy — not reliably scriptable cross-platform in an
      automated test; left for the user to verify interactively on a
      longer real run if desired.
