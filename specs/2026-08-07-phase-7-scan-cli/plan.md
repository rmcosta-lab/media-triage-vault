# Plan — Phase 7: Scan CLI

## 1. Dependency

- `pyproject.toml`: add `typer>=0.15.0` to `[project.dependencies]`; add
  `[project.scripts] media-organizer = "backend.app.cli.main:app"`.
- `uv sync` to lock it.

## 2. CLI package

- New `backend/app/cli/__init__.py` (empty, marks the package).
- New `backend/app/cli/main.py`:
  - `app = typer.Typer(name="media-organizer", help=...)`.
  - `@app.command("scan")` — `scan_command(path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, resolve_path=True), recursive: bool = typer.Option(True, "--recursive/--no-recursive"), output: Path = typer.Option(..., "--output"), database: Path | None = typer.Option(None, "--database", hidden=True))`.
    `database` defaults to `get_database_path()` when not given (test-only
    override, hidden from `--help`).

## 3. Orchestration helpers

- `backend/app/cli/scan_report.py`:
  - `write_error_log(path: Path, rows: Sequence[MediaFile]) -> int` — writes
    `<dir>/errors.log`, returns count written.
  - `write_inventory_json(path: Path, session: Session, rows: Sequence[MediaFile]) -> None` —
    writes `<dir>/inventory.json`; for each row, look up its
    `MediaMetadata` via `MediaMetadataRepository.get_by_media_file_id` and
    nest it (or `None`) under `"metadata"`. Datetimes serialized with
    `.isoformat()`.
  - `_media_file_to_dict` / `_media_metadata_to_dict` helpers.

## 4. Command body

- In `scan_command`:
  1. `output.mkdir(parents=True, exist_ok=True)`.
  2. Open a session via `get_session(get_engine())`.
  3. `scan = scan_folder(session, path, recursive=recursive, on_progress=lambda p: typer.echo(...))`.
  4. `detect_media_types_for_scan(session, scan.id, on_progress=lambda n: ...)`.
  5. `extract_metadata_for_scan(session, scan.id, on_progress=lambda n: ...)`.
  6. Reload all rows for `scan.id` via `MediaFileRepository.list_by_scan`.
  7. `write_error_log(output / "errors.log", rows)`.
  8. `write_inventory_json(output / "inventory.json", session, rows)`.
  9. `typer.echo` a final summary (counts by `media_kind`, mismatches,
     errors).
  10. `raise typer.Exit(code=0)` implicitly (no explicit failure path beyond
      Click's own path-validation exit).

## 5. Tests

- `backend/tests/unit/test_scan_report.py`:
  - `write_error_log` — rows with/without errors, exact line format.
  - `write_inventory_json` — a row with metadata, a row without, datetime
    serialization, valid JSON parse back.
- `backend/tests/integration/test_scan_cli.py`:
  - `typer.testing.CliRunner().invoke(app, ["scan", str(fixtures_copy), "--output", str(out_dir)])`.
  - Exit code `0`.
  - `out_dir/inventory.json` parses and contains every fixture file with
    expected `media_kind`.
  - `out_dir/errors.log` exists and mentions `corrupt_video.mp4` /
    `VIDEO_UNREADABLE`.
  - Fixture files under the temp source root are byte-identical before and
    after the run (read-only proof).
  - Invoking with a nonexistent path exits non-zero via Click's own
    validation (no crash/traceback).

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer --help` and `uv run media-organizer scan --help`
  run cleanly.
