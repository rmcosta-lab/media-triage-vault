# Validation — Phase 15: Transactional executor

### Functional

- [x] Same-volume moves use an atomic rename — `_execute_same_volume`
      (`os.rename`) — `test_same_volume_rename_completes`.
- [x] Cross-volume moves follow hash → copy-temp → verify → rename →
      delete-source — `_execute_cross_volume` —
      `test_cross_volume_copy_completes`.
- [x] The rename-vs-copy decision goes through `is_same_volume(a, b)`
      only — confirmed by reading `move_executor.py`: no call site
      inspects a drive letter or mount point; `core/volume.py` is the
      single implementation.
- [x] The journal (`MoveOperation.status`) is consulted before every
      operation; a completed operation is never repeated —
      `test_idempotent_rerun_of_completed_plan_is_a_no_op`.
- [x] A source file is only deleted after its destination copy is
      validated (size, and hash for cross-volume/`strict`) —
      `_execute_cross_volume` deletes the source only after the rename
      that follows a successful hash comparison;
      `test_hash_mismatch_fails_and_cleans_up_partial` confirms the
      source survives a failed verification.

### Roadmap done criterion

- [x] Temp-dir test covers a same-volume rename —
      `test_same_volume_rename_completes`.
- [x] Temp-dir test covers a simulated cross-volume copy (`is_same_volume`
      monkeypatched `False`, since a single test filesystem has no real
      second volume) — `test_cross_volume_copy_completes`.
- [x] Temp-dir test covers a mid-copy failure —
      `test_mid_copy_failure_leaves_no_partial_and_source_untouched`.
- [x] Temp-dir test covers a hash mismatch —
      `test_hash_mismatch_fails_and_cleans_up_partial`.

### Tests

- [x] `is_same_volume` covered for an existing pair of directories and a
      not-yet-existing destination path — `test_volume.py`, 2 tests.
- [x] `sha256_file` covered against a known digest and chunked vs.
      whole-file consistency — `test_hashing.py`, 2 tests.
- [x] Executor covered for: same-volume happy path, cross-volume happy
      path, mid-copy failure, hash mismatch, destination-exists-at-
      execution-time, idempotent re-run of a completed plan, resume after
      a simulated crash (both the "leftover partial" and the "move
      actually finished" cases), `standard` vs. `strict` hashing on a
      same-volume rename, and a `blocked` row left untouched —
      `test_move_executor.py`, 10 tests.
- [x] No test leaves a `.partial-*` file behind after a failure case —
      asserted explicitly in the mid-copy-failure and hash-mismatch
      tests via `tmp_path.rglob("*.partial-*")`.

### Safety

- [x] No network call is made — `move_executor.py`/`volume.py`/
      `hashing.py` import only `os`, `shutil`, `hashlib`, `pathlib`,
      `contextlib`, `datetime`, `dataclasses`, `collections.abc`,
      SQLModel, and already-audited repository/model code — confirmed by
      reading every new module's imports.
- [x] No source file is deleted before its copy is validated — verified
      by `test_hash_mismatch_fails_and_cleans_up_partial` and
      `test_mid_copy_failure_leaves_no_partial_and_source_untouched`
      (source still exists after both failure modes).
- [x] `overwrite`/silent-collision behavior is never implemented —
      `DESTINATION_EXISTS` fails the operation instead of overwriting —
      `test_destination_exists_at_execution_time_fails`.
- [x] Every filesystem call uses `pathlib`/`os`/`shutil` APIs directly —
      no shell invocation anywhere in this phase's code — confirmed by
      reading `move_executor.py`.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "85 files already
      formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 85
      source files".
- [x] `uv run pytest` green — 238 passed (14 new: 2 volume, 2 hashing,
      10 executor).
