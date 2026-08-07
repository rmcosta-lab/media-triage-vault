# Validation — Phase 3: Data model + SQLite

### Functional

- [x] `Scan` SQLModel table exists with exactly the fields listed in README
      §24.1. (`backend/app/models/scan.py`: `id`, `source_root`,
      `recursive`, `status`, `total_files`, `processed_files`,
      `total_bytes`, `created_at`, `started_at`, `finished_at`.)
- [x] `MediaFile` SQLModel table exists with exactly the fields listed in
      README §24.2, including `scan_id` as a foreign key to `Scan.id`.
      (`backend/app/models/media_file.py`: all 18 fields present;
      `scan_id: int = Field(foreign_key="scan.id")`.)
- [x] A SQLite database file is created under `runtime/database/` (not
      elsewhere), with the parent directory created automatically if
      missing. (Manually verified: `get_database_path()` →
      `runtime/database/media_organizer.db`; ran `create_db_and_tables`
      against it, file exists on disk afterward; `runtime/` did not exist
      before the call.)
- [x] `ScanRepository` and `MediaFileRepository` each support create, get,
      list, update, and delete. (`backend/app/repositories/base.py`
      generic `Repository[T]`; `test_scan_repository_crud` and
      `test_media_file_repository_crud_and_list_by_scan` exercise all five
      operations for both.)
- [x] `Scan` and `MediaFile` round-trip through a real SQLite engine in a
      test: values written match values read back after a fresh session,
      and the `Scan.media_files` / `MediaFile.scan` relationship resolves.
      (`test_scan_and_media_file_round_trip_through_sqlite`.)

### Tests

- [x] Unit test covers the full round-trip of a `Scan` with associated
      `MediaFile` rows through SQLite.
      (`backend/tests/unit/test_models.py::test_scan_and_media_file_round_trip_through_sqlite`.)
- [x] Unit test covers `ScanRepository` CRUD.
      (`backend/tests/unit/test_repositories.py::test_scan_repository_crud`.)
- [x] Unit test covers `MediaFileRepository` CRUD, including
      `list_by_scan`.
      (`backend/tests/unit/test_repositories.py::test_media_file_repository_crud_and_list_by_scan`.)
- [x] `uv run pytest` green, including the new tests. (21 passed — 18 from
      Phases 1–2 plus 3 new tests in this phase.)

### Safety

- [x] No network call is made anywhere in this phase (SQLite is a local
      file only). (Grepped `backend/` for `requests.`, `urllib.request`,
      `httpx.`, `socket.`, `http.client` — no matches.)
- [x] No source file outside `backend/app/{core,models,repositories}`,
      `backend/tests/`, `pyproject.toml`, `uv.lock`, `.gitignore`, and this
      spec directory is created or modified; no user file anywhere is
      touched. (`git status --porcelain` shows only
      `backend/app/core/db.py`, `backend/app/models/`,
      `backend/app/repositories/`, `backend/tests/unit/test_models.py`,
      `backend/tests/unit/test_repositories.py`,
      `specs/2026-08-07-phase-3-data-model-sqlite/`, and modifications to
      `.gitignore`, `pyproject.toml`, `uv.lock` — all expected.)
- [x] `runtime/database/` is created only as a side effect of using the
      engine/session module — not committed to git (`runtime/` is
      gitignored). (Manually created it via `get_database_path()` +
      `create_db_and_tables`; `git status` afterward does not list
      anything under `runtime/`.)

### Technical

- [x] `uv run ruff check .` clean. (`All checks passed!`)
- [x] `uv run ruff format --check .` clean. (`21 files already
      formatted`.)
- [x] `uv run mypy backend` clean. (`Success: no issues found in 21 source
      files`. Note: `backend/app/models/scan.py` and
      `backend/app/models/media_file.py` deliberately omit
      `from __future__ import annotations` — SQLModel's relationship
      resolution reads `cls.__annotations__` at class-creation time, and
      under PEP 563 those become plain source-text strings instead of
      evaluable forward references, which made `Relationship()` pass the
      literal text `"list[MediaFile]"` to SQLAlchemy as a class name and
      fail. Forward references to the other table stay as quoted strings
      (`list["MediaFile"]`, `"Scan"`) instead.)
- [x] `uv run pytest` green. (21 passed.)
