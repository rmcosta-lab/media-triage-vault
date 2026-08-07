# Requirements — Phase 15: Transactional executor

## Objective

Turn a generated, dry-run `MovePlan` (Phase 14) into real file operations,
safely: every `MoveOperation` row is driven through the journal states from
`planned` to a terminal state via the README §17 rename/copy sequences, so
that the journal — not the caller — is always the source of truth for what
has and hasn't happened yet. This is the core safety layer Phase 16's CLI
sits on top of; no user-facing confirmation, progress display, or resume
command exists yet (that's Phase 16), but the underlying `execute_move_plan`
function is already idempotent and resumable at the service layer.

## Scope

### In

- `backend/app/core/volume.py`: `is_same_volume(source, destination) ->
  bool` — the one helper the executor consults to choose rename vs. copy;
  never inspects a drive letter or mount point at any call site.
- `backend/app/core/hashing.py`: `sha256_file(path) -> str`, streamed in
  fixed-size chunks (no whole-file read into memory).
- `backend/app/models/move_plan.py`: extend `MOVE_OPERATION_STATUSES` with
  the execution states from README §18 (`validating`, `copying`,
  `verifying`, `renaming`, `deleting_source`, `completed`, `failed`,
  `skipped`, `cancelled`) — the table shape already exists from Phase 14.
- `backend/app/services/move_executor.py`: `execute_move_plan(session,
  move_plan_id, ...)` — for every `MoveOperation` still in `planned`
  status, re-validates the source, picks same-volume rename or
  cross-volume hash→copy→verify→rename→delete via `is_same_volume`, and
  persists every state transition. Consults each operation's current
  status before acting (idempotent: a `completed` row is never redone; a
  row left mid-flight by a crashed run is safely resumed or restarted).
- Unit tests covering: same-volume rename, a simulated cross-volume copy
  (via `is_same_volume` monkeypatched to `False`, since a single test
  filesystem can't produce a real second volume), a mid-copy failure, a
  hash mismatch, and resuming an interrupted run.

### Out (later phases)

- CLI command, explicit user confirmation, live per-file progress display,
  cancellation-between-files wiring, the move report, and the
  kill-and-resume *CLI* test — Phase 16. `execute_move_plan` exposes
  `on_progress` and `should_cancel` hooks for Phase 16 to use, but nothing
  in this phase drives them from a terminal.
- `collision_policy` values other than `error` — still only `error` is
  supported (README §17.5); the executor re-checks for a destination that
  now exists (`DESTINATION_EXISTS`) but does not rename-with-suffix or
  deduplicate.
- FastAPI/API surface — Stage F.

## Source of truth

- README §17 "Segurança da movimentação" — §17.1 principles, §17.2
  same-volume sequence, §17.3 cross-volume sequence and the
  `nome-original.ext.partial-<operation-id>` temp-name convention, §17.4
  hash modes, §17.5 collision policy.
- README §18 "Diário transacional" — the full `MoveOperation` field list
  (already persisted, Phase 14) and the state list this phase drives
  through.
- `specs/roadmap.md` Phase 15 entry — journal states, atomic rename,
  cross-volume sequence, idempotent/resumable via the journal, the single
  `is_same_volume` helper, done criterion (temp-dir tests for rename,
  simulated cross-volume copy, mid-copy failure, hash mismatch).
- `specs/tech-stack.md` "Cross-platform" table, "Volume identity" row
  (`is_same_volume` owned by Phase 15).
- `specs/mission.md` principle 3 (never destroy data — hash/size
  validation before any source delete, journal every step, resumable).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| `is_same_volume` implementation | `os.stat(nearest_existing_ancestor).st_dev` equality for both paths | `st_dev` already encodes "same filesystem" correctly cross-platform (drive number on Windows via Python's `os.stat`, device id on POSIX) without the executor ever branching on `sys.platform` itself — satisfies "one helper, per-platform implementation" without duplicating logic per OS. |
| Hashing module location | `core/hashing.py`, not inside the executor service | Pure stdlib helper with no DB/service dependency, same pattern as `core/paths.py` and `core/destination_paths.py`. |
| Journal consultation | Re-read `operation.status` from the row already loaded for every operation before acting; a stale in-flight status from a crashed run is resolved by `_resume_or_reset` (completed if the destination file already matches size, otherwise cleaned up and restarted) | Matches roadmap "journal consulted before any operation (idempotent, resumable)" without a separate lock table — the row's own `status` is the lock. |
| `standard` vs `strict` hashing | `standard`: hash mandatory only for a cross-volume copy (verifies the copy), size-only validation for a same-volume rename; `strict`: hash computed for every operation regardless of volume | Directly README §17.4. |
| Destination directory creation | Executor creates missing destination directories (`Path.mkdir(parents=True, exist_ok=True)`) right before writing | Phase 14's plan-time check only confirms the nearest *existing* ancestor is writable — someone has to actually create the new folder, and it can only safely happen at execution time, never during read-only planning. |
| Error taxonomy | New codes distinct from Phase 14's plan-time codes: `SOURCE_MISSING`, `SOURCE_CHANGED` (re-checked at execution time too, since time passed since planning), `DESTINATION_EXISTS`, `COPY_FAILED`, `SIZE_MISMATCH`, `HASH_MISMATCH`, `RENAME_FAILED`, `SOURCE_NOT_DELETED`, `UNEXPECTED_ERROR` | Mirrors Phase 14's one-error-code-per-row pattern; re-running the same checks at execution time (not just trusting the plan) is what makes execution safe against time-of-check/time-of-use drift between planning and running. |
| `blocked` rows | Never executed — loop skips any `MoveOperation` not in `planned` (after resume handling) that isn't already terminal | A blocked row needs a new plan, not a retried execution (Phase 14 decision, unchanged). |

## Constraints

- **Never destroy data** (`specs/mission.md` #3): source is deleted only
  after copy validation (size, and hash for cross-volume/`strict`)
  succeeds; collisions at execution time (`DESTINATION_EXISTS`) fail the
  operation rather than overwrite.
- **Idempotent and resumable**: calling `execute_move_plan` twice on the
  same plan performs no duplicate work and no duplicate file writes.
- **100% local and offline**: no network calls; all I/O is local
  filesystem and SQLite.
- **No bare rename/copy outside the journal**: every state transition is
  written to the `MoveOperation` row before/after the corresponding
  filesystem action, so a crash at any point leaves a diagnosable state.
