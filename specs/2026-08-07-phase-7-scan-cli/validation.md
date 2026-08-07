# Validation — Phase 7: Scan CLI

### Functional (US-001, README §37)

- [x] Accepts a local path (`typer.Argument`) — `path` argument in `scan_command`.
- [x] Validates the path exists and is a directory (Click's built-in check,
      non-zero exit on a bad path) — `exists=True, dir_okay=True, file_okay=False`;
      `test_scan_command_nonexistent_path_exits_nonzero`.
- [x] Walks subfolders (`--recursive`, Phase 4) — wired via `scan_folder`.
- [x] Identifies media type (Phase 5) — wired via `detect_media_types_for_scan`.
- [x] Extracts metadata (Phase 6) — wired via `extract_metadata_for_scan`.
- [x] Persists to SQLite — same session across all three stages.
- [x] Shows progress (printed per batch) — `typer.echo` inside each stage's
      `on_progress` callback; verified manually (`uv run media-organizer scan ...`).
- [x] Records errors (`errors.log` in `--output`) —
      `test_scan_command_end_to_end` asserts `corrupt_video.mp4` /
      `VIDEO_UNREADABLE` appear in it.
- [x] Generates JSON (`inventory.json` in `--output`) — same test parses it
      and checks `media_kind`, `extension_mismatch`, nested `metadata`.
- [x] Does not move, alter, or delete files — fixtures are SHA-256-identical
      before/after a scan run in `test_scan_command_end_to_end`; manually
      confirmed against the real `backend/tests/fixtures/` files too.

### Tests

- [x] Unit tests for `write_error_log` and `write_inventory_json` —
      `test_write_error_log_writes_only_errored_rows`,
      `test_write_error_log_empty_when_no_errors`,
      `test_write_inventory_json_nests_metadata_when_present`.
- [x] Integration test invokes the real Typer `app` via `CliRunner` against
      a temp fixtures copy and asserts the full acceptance list above —
      `test_scan_command_end_to_end`.
- [x] Integration test confirms `corrupt_video.mp4` appears in `errors.log`
      with `VIDEO_UNREADABLE` — same test.
- [x] Integration test on a nonexistent path exits non-zero without a
      traceback — `test_scan_command_nonexistent_path_exits_nonzero`.

### Safety

- [x] No network call is made — `cli/main.py` and `cli/scan_report.py` only
      import `typer`, stdlib, and the already-audited Phase 4-6 services.
- [x] No source file under the scanned path is modified, moved, or deleted
      — SHA-256 comparison in `test_scan_command_end_to_end`; `git status`
      after the full test run shows no fixture changes.
- [x] Writes are confined to `--output` (`errors.log`, `inventory.json`)
      and the SQLite database file (`--database`, defaulting to
      `runtime/database/media_organizer.db`).
- [x] External tools are still invoked only through `run_tool`/`resolve_tool`
      — the CLI layer introduces no new subprocess calls; confirmed by
      reading `cli/main.py`/`cli/scan_report.py` (no `subprocess` import).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!" (added
      `tool.ruff.lint.flake8-bugbear.extend-immutable-calls` for
      `typer.Argument`/`typer.Option` default-value calls, the documented
      Typer pattern that otherwise trips B008).
- [x] `uv run ruff format --check .` clean — "42 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 42 source files".
- [x] `uv run pytest` green — 88 passed (5 new: 3 unit, 2 integration).
- [x] `uv run media-organizer --help` and `uv run media-organizer scan --help`
      run without error — verified manually; required adding an explicit
      `@app.callback()` so Typer keeps `scan` as a named subcommand instead
      of collapsing to a single top-level command (its default behavior
      with only one registered `@app.command()`).
