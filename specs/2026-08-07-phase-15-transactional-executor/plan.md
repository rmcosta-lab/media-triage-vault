# Plan — Phase 15: Transactional executor

## 1. Volume identity helper (core)

- New `backend/app/core/volume.py`:
  - `_nearest_existing_ancestor(path: Path) -> Path`: walk `path.parent`
    upward until an existing directory is found (handles a not-yet-created
    destination file/dir).
  - `is_same_volume(source: Path, destination: Path) -> bool`: compare
    `os.stat(...).st_dev` of each path's nearest existing ancestor.

## 2. Hashing helper (core)

- New `backend/app/core/hashing.py`:
  - `sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str`:
    stream the file through `hashlib.sha256()` in `chunk_size` reads,
    return `hexdigest()`.

## 3. Model update

- `backend/app/models/move_plan.py`: extend `MOVE_OPERATION_STATUSES` to
  `("planned", "blocked", "validating", "copying", "verifying",
  "renaming", "deleting_source", "completed", "failed", "skipped",
  "cancelled")`; update the module docstring to note Phase 15 now owns the
  execution states. No schema/column change — `MoveOperation` already has
  every field this phase writes (`source_hash`, `destination_size`,
  `destination_hash`, `actual_destination_path`, `started_at`,
  `finished_at`, `error_code`, `error_message`).

## 4. Executor service

- New `backend/app/services/move_executor.py`:
  - `TERMINAL_STATUSES`, `IN_FLIGHT_STATUSES` module tuples.
  - `_ExecutionError(Exception)`: carries `error_code`.
  - `MoveExecutionSummary` frozen dataclass: `total_completed`,
    `total_failed`, `total_skipped`, `total_bytes_moved`,
    `by_error_code: dict[str, int]`.
  - `_partial_path(destination, operation_id) -> Path`:
    `destination.with_name(f"{destination.name}.partial-{operation_id}")`.
  - `_validate_source(operation) -> str | None`: re-checks
    `SOURCE_MISSING` / `SOURCE_CHANGED` (size only — mtime already spent
    at plan time, this is a cheap re-check right before touching the
    file) against the row's own `source_size`; returns an error code or
    `None`.
  - `_execute_same_volume(operation, source, destination, validation_mode)`:
    create `destination.parent`; raise `DESTINATION_EXISTS` if it already
    exists; `status="renaming"`; `os.rename`; verify size; if
    `validation_mode == "strict"`, hash the destination and store it in
    both `source_hash`/`destination_hash`; set
    `actual_destination_path`/`destination_size`.
  - `_execute_cross_volume(operation, source, destination, validation_mode)`:
    `status="validating"` → `sha256_file(source)` into `source_hash`;
    create `destination.parent`; clean any stale partial;
    `status="copying"` → stream-copy into the `.partial-<id>` temp file in
    the destination directory, `flush()` + `os.fsync`; on any `OSError`
    clean up the partial and raise `COPY_FAILED`; `status="verifying"` →
    size check (`SIZE_MISMATCH`) then hash check (`HASH_MISMATCH`),
    cleaning up the partial on either failure; `status="renaming"` →
    raise `DESTINATION_EXISTS` if the destination now exists, else
    `os.rename(partial, destination)`; `status="deleting_source"` →
    `os.remove(source)`, raise `SOURCE_NOT_DELETED` if it still exists;
    set `actual_destination_path`/`destination_size`/`destination_hash`.
  - `_resume_or_reset(operation) -> bool`: no-op (`return False`) unless
    `operation.status in IN_FLIGHT_STATUSES`. If in-flight: when
    `actual_destination_path` is set, exists, and its size matches
    `source_size`, mark `completed`/`finished_at` (crash happened after
    the real move, before the journal write) and return `True`;
    otherwise clean up any leftover `.partial-<id>` next to the planned
    destination and reset the row to `status="planned"` (clear
    `actual_destination_path`/`error_code`/`error_message`), return
    `True`.
  - `execute_move_plan(session, move_plan_id, *, validation_mode: str |
    None = None, on_progress: Callable[[MoveOperation], None] | None =
    None, should_cancel: Callable[[], bool] | None = None) ->
    MoveExecutionSummary`:
    1. Load the `MovePlan`; raise `ValueError` if missing; resolve
       `validation_mode` (explicit override or the plan's own).
    2. Load every `MoveOperation` for the plan via
       `MoveOperationRepository.list_by_plan`.
    3. For each operation, in order:
       - `_resume_or_reset`; if it returned `True`, persist via
         `operation_repository.update` and fold the (possibly now
         `completed`) row into the running totals.
       - If already `completed`/`failed`/`skipped`/`cancelled` (and
         wasn't just touched above), fold into totals without writing.
       - If not `planned` at this point (i.e. still `blocked`), skip —
         never executed by this phase.
       - If `should_cancel` is provided and returns `True`, stop the loop
         (remaining `planned` rows are left untouched for a future
         resume).
       - Otherwise: `started_at = now()`; `_validate_source`; if it
         returns an error code, raise `_ExecutionError`; else
         `status="validating"`, branch on `is_same_volume(source,
         destination)` into same-volume or cross-volume execution;
         `except _ExecutionError` / `except OSError` → mark `failed` with
         the code/message and `finished_at`; on success mark
         `completed`/`finished_at`; persist via
         `operation_repository.update`; call `on_progress(operation)` if
         given; fold into totals.
    4. Return the summary.

## 5. Tests

- `backend/tests/unit/test_volume.py`: same directory → same volume
  (`True`); a not-yet-existing nested destination path still resolves via
  its nearest existing ancestor.
- `backend/tests/unit/test_hashing.py`: known content → known SHA-256
  digest; chunked reads produce the same digest as a whole-file
  `hashlib.sha256(data).hexdigest()` reference for content larger than
  one chunk.
- `backend/tests/unit/test_move_executor.py` (temp-dir fixtures, a
  `MovePlan` + one or more `MoveOperation` rows created directly per
  test, no full `generate_move_plan` dependency needed):
  - **Same-volume rename**: happy path → `status="completed"`, file
    exists at destination, source gone, `destination_size` set.
  - **Simulated cross-volume copy** (`is_same_volume` monkeypatched
    `False`): happy path → `status="completed"`, `source_hash ==
    destination_hash`, no leftover `.partial-*` file, source gone.
  - **Mid-copy failure**: `shutil.copyfileobj` monkeypatched to raise
    `OSError` mid-write → `status="failed"`, `error_code="COPY_FAILED"`,
    no partial file left behind, source untouched, destination not
    created.
  - **Hash mismatch**: `sha256_file` monkeypatched to return a different
    digest for the partial than for the source → `status="failed"`,
    `error_code="HASH_MISMATCH"`, partial cleaned up, source untouched.
  - **Destination already exists at execution time**: a file is created
    at the destination path between planning and execution →
    `status="failed"`, `error_code="DESTINATION_EXISTS"`, source
    untouched.
  - **Idempotent re-run**: executing an already-`completed` plan a second
    time performs no filesystem writes (assert mtimes/hashes of both the
    executor-created destination file and its containing directory
    listing are unchanged) and returns the same totals.
  - **Resume after a simulated crash**: an operation manually left in
    `status="copying"` with a stray `.partial-<id>` file and no
    `actual_destination_path` → re-running `execute_move_plan` cleans up
    the stray partial, restarts the operation, and reaches `completed`.
  - **Resume when the move actually finished before the crash**: an
    operation left `status="renaming"` but `actual_destination_path`
    already points at a real, correctly-sized file → re-running marks it
    `completed` without touching the filesystem again.
  - `strict` validation mode hashes a same-volume rename too
    (`source_hash`/`destination_hash` both populated); `standard` mode
    leaves them `None` for a same-volume rename.
  - A `blocked` operation is left untouched by `execute_move_plan`.

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
