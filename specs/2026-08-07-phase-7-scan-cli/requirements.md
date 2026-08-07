# Requirements — Phase 7: Scan CLI

## Objective

Wire Phases 4–6 (scan, media-type detection, batch metadata extraction)
behind one command, `media-organizer scan <path> --recursive --output <dir>`,
so US-001 passes end to end: a user points the tool at a local folder and
gets a persisted inventory, visible progress, an error log, and a JSON
export — without a single write to the scanned tree.

## Scope

### In

- A Typer CLI app, `media-organizer`, installed as a `project.scripts`
  entry point (`uv run media-organizer --help` works, per `AGENTS.md`).
- `media-organizer scan <path> [--recursive/--no-recursive] --output <dir> [--database <file>]`:
  1. Validates `<path>` exists and is a directory (Typer/Click's built-in
     path validation — no hand-rolled check).
  2. Creates `<dir>` if missing.
  3. Runs `scan_folder` → `detect_media_types_for_scan` →
     `extract_metadata_for_scan` in sequence over one SQLite session, using
     the standard database path (`backend/app/core/db.py`), same as every
     other phase's tests.
  4. Prints progress as each stage's batches flush, using the `on_progress`
     callbacks the three services already expose — no new progress
     machinery inside the services themselves.
  5. Writes `<dir>/errors.log`: one line per `MediaFile` row that ended
     with a non-null `error_code`, in `relative_path: error_code —
     error_message` form.
  6. Writes `<dir>/inventory.json`: one JSON array, one object per
     `MediaFile` row (identity/type/technical columns plus a nested
     `metadata` object from its `MediaMetadata` row when one exists).
  7. Prints a final summary (files scanned, images, videos, unsupported,
     mismatches, errors) and exits `0`.
- Unit tests for the JSON/error-log serialization helpers.
- An integration test invoking the Typer app (via `CliRunner`) against a
  temp copy of the fixtures directory, asserting the full acceptance list.

### Out (later phases)

- Any write to a file under the scanned source root — never in scope.
- Classification wiring (`classify` command) — Phase 12.
- CSV/HTML reports — Phase 13.

## Source of truth

- README §37 "US-001 — Analisar uma pasta e gerar inventário" — the full
  acceptance list this phase must satisfy end to end.
- README §32 "Fase 1" — expected command shape
  (`media-organizer scan "D:\Fotos" --recursive`).
- `specs/roadmap.md` Phase 7 entry and its *Done when* criterion.
- `specs/tech-stack.md` — Typer as the pinned CLI framework.
- `specs/mission.md` principles 1 (offline), 2 (read-only until Phase 14).
- Phases 4–6's services (`scanner.py`, `media_type.py`, `metadata.py`) —
  this phase only orchestrates them, it adds no new domain logic.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| CLI package location | `backend/app/cli/main.py`, `app = typer.Typer(name="media-organizer")`, entry point `media-organizer = "backend.app.cli.main:app"` | Typer objects are directly callable, the standard `project.scripts` pattern for Typer apps; a package (not a single top-level module) leaves room for the `classify` (Phase 12) and `execute`/`resume` (Phase 16) commands to land as siblings later. |
| Path validation | Click's `exists=True, file_okay=False, dir_okay=True, resolve_path=True` on the `typer.Argument` | Built-in, tested by Click itself; no hand-rolled existence check duplicating what Phase 4's `scan_folder` already raises `InvalidSourceRootError` for — the CLI layer never gets a chance to call it with a bad path. |
| Database | The standard path from `backend/app/core/db.py` (`runtime/database/media_organizer.db`) by default, overridable with a hidden-from-README `--database <file>` option | Matches every existing test and service signature; `--output` is for the *report* artifacts (README's `--output ".\runtime\reports\scan-001"` example), not the database. `--database` exists purely so integration tests can point the CLI at a temp SQLite file instead of ever touching the user's real `runtime/database/media_organizer.db` — the same isolation every other integration test already gets via `get_engine(tmp_path / "test.db")`. |
| Progress display | Print a line per batch from each stage's existing `on_progress` callback (`ScanProgress`, `int` count, `int` count) | The services already expose exactly this hook (Phases 4–6); the CLI is the first and only consumer, so no new signal is invented. |
| Error log format | Plain text, one line per errored row (`relative_path: error_code — error_message`) | README only requires errors be "registered" (§37 "registra erros"); plain text is trivially greppable and needs no schema, unlike the structured JSON export. |
| JSON export shape | One object per `MediaFile` row, columns matching the model, plus a nested `metadata` object (or `null`) from `MediaMetadataRepository.get_by_media_file_id` | Directly satisfies "gera JSON" (§37); nesting metadata avoids a second top-level array the caller would have to join by `media_file_id` themselves. |
| Output directory writes | `<dir>/errors.log` and `<dir>/inventory.json` only; `<dir>` is never inside the scanned source root (not validated, but documented as a usage expectation) | These are report artifacts, not source files — writing them doesn't violate "read-only until Phase 14" (`specs/mission.md` #2), which is about the *scanned tree*. |
| Testing the CLI | Typer's `CliRunner` (via `typer.testing.CliRunner`) invoking the real `app` against a temp fixtures copy | Exercises the actual command wiring (argument parsing, exit codes) rather than calling the underlying function directly. |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): the CLI never
  writes to `<path>`, only to `<dir>` and the SQLite database.
- **100% local and offline** (`specs/mission.md` #1): no network calls.
- **Core before interface** (`specs/mission.md` #7): this is the CLI layer
  over the already-tested Phase 4–6 engine; no new detection/extraction
  logic is added here.
- Adding `typer` as a dependency requires it to be recorded in
  `specs/tech-stack.md` — it already is (pinned decision, "CLI framework").
