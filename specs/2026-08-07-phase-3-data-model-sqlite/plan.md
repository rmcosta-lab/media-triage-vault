# Plan — Phase 3: Data model + SQLite

## 1. Dependency

- Add `sqlmodel` to `[project.dependencies]` in `pyproject.toml`.
- `uv sync` to update `uv.lock`.

## 2. Database engine + session (`backend/app/core/db.py`)

- `get_database_path() -> Path`: resolves `runtime/database/media_organizer.db`
  anchored to the repo root (via `Path(__file__).resolve().parents[N]`, same
  pattern as Phase 2's `tools.py`), creating `runtime/database/` if it does
  not exist.
- `get_engine(path: Path | None = None) -> Engine`: `create_engine(f"sqlite:///{path}")`;
  defaults to `get_database_path()` when no path is given, so tests can pass
  a temp path or `sqlite:///:memory:` instead.
- `create_db_and_tables(engine: Engine) -> None`: `SQLModel.metadata.create_all(engine)`.
- `get_session(engine: Engine) -> Iterator[Session]`: context manager /
  generator yielding a `Session` bound to the given engine, for use by
  repositories and tests.

## 3. Models (`backend/app/models/`)

- `backend/app/models/__init__.py`: re-exports `Scan`, `MediaFile`.
- `backend/app/models/scan.py`:
  - `Scan(SQLModel, table=True)` with fields per README §24.1: `id`
    (int primary key, optional/autoincrement), `source_root: str`,
    `recursive: bool`, `status: str`, `total_files: int = 0`,
    `processed_files: int = 0`, `total_bytes: int = 0`,
    `created_at: datetime` (UTC default factory), `started_at: datetime | None`,
    `finished_at: datetime | None`.
  - `media_files: list["MediaFile"]` relationship (back-populates `scan`).
- `backend/app/models/media_file.py`:
  - `MediaFile(SQLModel, table=True)` with fields per README §24.2: `id`
    (int primary key), `scan_id: int = Field(foreign_key="scan.id")`,
    `absolute_path: str`, `relative_path: str`, `file_name: str`,
    `extension: str`, `mime_type: str | None`, `file_type: str | None`,
    `size_bytes: int`, `modified_at: datetime | None`,
    `created_at: datetime` (UTC default factory), `width: int | None`,
    `height: int | None`, `duration_seconds: float | None`,
    `metadata_json: str | None`, `processing_status: str`,
    `error_code: str | None`, `error_message: str | None`.
  - `scan: Scan | None` relationship (back-populates `media_files`); use
    `TYPE_CHECKING` import of `Scan` to avoid a circular import, matching
    SQLModel's documented relationship pattern.

## 4. Repository layer (`backend/app/repositories/`)

- `backend/app/repositories/base.py`: `Repository[T: SQLModel]` generic
  class wrapping a `Session`:
  - `create(obj: T) -> T`
  - `get(id: int) -> T | None`
  - `list() -> Sequence[T]`
  - `update(obj: T) -> T`
  - `delete(id: int) -> None`
- `backend/app/repositories/scan_repository.py`: `ScanRepository(Repository[Scan])`.
- `backend/app/repositories/media_file_repository.py`:
  `MediaFileRepository(Repository[MediaFile])` plus
  `list_by_scan(scan_id: int) -> Sequence[MediaFile]`.
- `backend/app/repositories/__init__.py`: re-exports both repository
  classes.

## 5. Tests

- `backend/tests/unit/test_models.py`:
  - Fixture: fresh `Engine` per test (`sqlite:///:memory:` or a
    `tmp_path`-based file), tables created via `create_db_and_tables`.
  - Insert a `Scan`, insert two `MediaFile` rows referencing it, reload
    from a new `Session`, assert every field round-trips and the
    `scan.media_files` / `media_file.scan` relationship resolves correctly.
- `backend/tests/unit/test_repositories.py`:
  - Same engine fixture.
  - `ScanRepository`: create, get, list, update (e.g. bump
    `processed_files`), delete — assert each step's expected state.
  - `MediaFileRepository`: create under a `Scan`, get, `list_by_scan`,
    update, delete.

## 6. Repo hygiene

- Add `runtime/` to `.gitignore` (generated at run time; never committed).

## 7. Verification

- `uv run pytest` — green, including the new model and repository tests.
- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — clean.
- `uv run mypy backend` — clean (SQLModel relationship typing may need
  `TYPE_CHECKING` imports or `Relationship(sa_relationship_kwargs=...)`
  adjustments to satisfy strict mode, as Phase 2 needed a mypy override for
  `pillow_heif`).
- Manual: confirm `runtime/database/media_organizer.db` is created on first
  use and is untracked in `git status`.
