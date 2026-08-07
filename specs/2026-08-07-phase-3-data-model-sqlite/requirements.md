# Requirements — Phase 3: Data model + SQLite

## Objective

Give the scanner (Phase 4) and every later phase a persistence layer: `Scan`
and `MediaFile` as SQLModel tables, a SQLite database created under
`runtime/database/`, and a small repository layer with basic CRUD — so
inventory results have somewhere to round-trip through before any
classification, reporting, or move logic exists.

## Scope

### In

- `Scan` SQLModel table with the exact fields from README §24.1: `id`,
  `source_root`, `recursive`, `status`, `total_files`, `processed_files`,
  `total_bytes`, `created_at`, `started_at`, `finished_at`.
- `MediaFile` SQLModel table with the exact fields from README §24.2: `id`,
  `scan_id`, `absolute_path`, `relative_path`, `file_name`, `extension`,
  `mime_type`, `file_type`, `size_bytes`, `modified_at`, `created_at`,
  `width`, `height`, `duration_seconds`, `metadata_json`,
  `processing_status`, `error_code`, `error_message`.
- `MediaFile.scan_id` as a foreign key to `Scan.id`, with a SQLModel
  relationship in both directions.
- A database engine/session module that resolves the SQLite file path to
  `runtime/database/media_organizer.db` (anchored to the repo root, not the
  process's working directory — same pattern as Phase 2's tool resolver),
  creates the parent directory if missing, and creates the schema via
  `SQLModel.metadata.create_all`.
- A repository layer with basic CRUD (create, get by id, list, update,
  delete) for `Scan` and `MediaFile`.
- Tests that round-trip both models through a real SQLite engine (temp file
  or in-memory), including the `MediaFile → Scan` relationship, and exercise
  the repository CRUD methods.

### Out

- `Classification`, `DestinationRule`, `MovePlan`, `MoveOperation` tables —
  Phases 8, 14, and 15 respectively (README §24.3–24.6).
- The scanner itself (recursive walk, ignore patterns) — Phase 4.
- Any metadata extraction or `media_kind` detection — Phases 5–6.
- A migrations framework (Alembic or similar) — schema is created fresh via
  `SQLModel.metadata.create_all`; migrations are not needed until a shipped
  schema needs to change under existing user data, which is beyond this
  phase.
- Any FastAPI/API exposure of this data — Phase 17 onward.
- Enum-typed `status`/`processing_status`/`error_code` values — the exact
  value sets belong to the phases that populate them (scanner status in
  Phase 4/7, error codes in Phase 4/6); this phase types them as plain
  strings.

## Source of truth

- README §24.1 "Scan" and §24.2 "MediaFile" — the exact field lists these
  models implement.
- `specs/roadmap.md` — Phase 3 entry (Stage A — Foundation): "SQLModel
  models for `Scan` and `MediaFile`; database creation under
  `runtime/database/`; repository layer with basic CRUD. Done when models
  round-trip through SQLite in tests."
- `specs/tech-stack.md` — "Pinned decisions": SQLModel as the ORM, SQLite as
  "single file under `runtime/database/`".
- `AGENTS.md` — "Repository layout" (`backend/app/{models,repositories}`,
  `runtime/{database,reports,thumbnails,logs}/`); "Implementation
  conventions" — "Types: SQLModel is the single model layer (validation +
  persistence). No parallel Pydantic schemas duplicating a table."

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Implement as written | User confirmed the roadmap phase description as-is. |
| Implementation approach | Tech-lead's call | User deferred to `specs/tech-stack.md` and `specs/mission.md`. |
| Validation criteria | Standard checks only | User confirmed no extra criteria beyond the roadmap's done condition and the standard lint/type/test gate. |
| Model module layout | `backend/app/models/scan.py`, `backend/app/models/media_file.py`, re-exported from `backend/app/models/__init__.py` | Mirrors `AGENTS.md`'s `backend/app/models/` layout; one file per table keeps later tables (Phase 8+) additive instead of growing one file. |
| Repository module layout | `backend/app/repositories/base.py` (generic CRUD over a `Session`) + `scan_repository.py` + `media_file_repository.py`, re-exported from `backend/app/repositories/__init__.py` | Matches `AGENTS.md`'s `backend/app/repositories/` layout; a small generic base avoids duplicating create/get/list/update/delete twice for two tables that need no bespoke query logic yet. |
| DB engine/session location | `backend/app/core/db.py` | `backend/app/core/` already holds the Phase 2 tool resolver — cross-cutting infrastructure (external tools, database) lives there per `AGENTS.md`'s layout. |
| Repo-root anchoring | `get_database_path()` resolves `runtime/database/media_organizer.db` via `Path(__file__).resolve().parents[N]`, not `Path.cwd()` | Same reasoning Phase 2 used for `tools.py`: the database path must not depend on where `media-organizer` is invoked from. |
| Primary keys | Integer autoincrement (`id: int \| None = Field(default=None, primary_key=True)`) | Simplest option for a local, single-user, single-process SQLite database; README's field lists just say `id` with no format mandate. |
| Timestamp fields | `datetime` (UTC-aware, `datetime.now(timezone.utc)` as the default factory where a default applies) | Avoids ambiguous naive timestamps once move journals and reports (later phases) need to reason about ordering across a run. |
| `metadata_json` storage | Plain `str` column (JSON-encoded text), optional | SQLite has no native JSON type; ExifTool's raw JSON subset (Phase 6) is serialized by the caller, not by this model. |
| Migrations | None yet — `SQLModel.metadata.create_all(engine)` on startup/test setup | No shipped schema with existing user data exists yet to migrate; revisit if/when a later phase changes a table that already holds real data. |
| `runtime/` in git | Added to `.gitignore` | `runtime/database/`, and later `runtime/{reports,thumbnails,logs}/`, are generated at run time on the user's machine, never committed artifacts. |
| New dependency | `sqlmodel`, added to `pyproject.toml` `[project.dependencies]` | Already pinned as the ORM choice in `specs/tech-stack.md`; this is the phase that first imports it. |

## Constraints

- **Read-only until Phase 14**: this phase only creates schema and exercises
  it with synthetic test data; no code path touches a user's real files.
- **No network**: SQLite is a local file; no remote database, no network
  call anywhere in this phase.
- **Single model layer**: SQLModel classes are both the persistence model
  and the validation model — no parallel Pydantic schema duplicating a
  table (`AGENTS.md`).
- **Dependencies**: only `sqlmodel` is added, and it is already pinned in
  `specs/tech-stack.md`; no other new dependency without updating that file
  first.
- **Language**: all code, comments, and commit messages in English.
