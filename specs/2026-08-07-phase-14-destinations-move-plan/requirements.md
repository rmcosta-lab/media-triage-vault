# Requirements — Phase 14: Destinations + move plan (dry run)

## Objective

Let the user map each `routing_group` to a destination folder, then generate
a complete, validated move plan against an existing scan+classification —
without moving, renaming, or deleting a single file. This is Stage E's
opening phase, the first phase allowed to reason about destinations at all
(`specs/mission.md` #2: "read-only until Phase 14"), and it closes US-003.
Phase 15 (transactional executor) and Phase 16 (execute/resume CLI,
confirmation) consume the plan this phase produces; neither exists yet, so
nothing generated here is ever executed.

## Scope

### In

- `backend/app/models/destination_rule.py`: `DestinationRule` table
  (README §24.4) — `scan_id`, `routing_group`, `destination_root`,
  `country_subfolder_enabled`, `enabled`.
- `backend/app/models/move_plan.py`: `MovePlan` table (README §24.5 —
  `scan_id`, `status`, `collision_policy`, `validation_mode`, timestamps)
  and `MoveOperation` table (README §18/§24.6 — the transactional-journal
  shape), both created now so Phase 15 extends the same journal rather than
  inventing a second one. Phase 14 only ever writes `MoveOperation.status
  ∈ {"planned", "blocked"}`; execution states (`in_progress`, `completed`,
  `failed`, `skipped`, `cancelled`, …) are Phase 15's to write.
- `backend/app/core/destination_paths.py`: pure helpers — destination-name
  sanitization to the portable intersection, the 260-character Windows
  path-length check, and case-insensitive NFC-normalized path collision
  comparison.
- `backend/app/repositories/destination_rule_repository.py`,
  `move_plan_repository.py`, `move_operation_repository.py`: CRUD +
  scan-scoped lookups, matching the existing repository pattern.
- `backend/app/services/destinations.py`: replace a scan's
  `DestinationRule` mapping from a group→config dict.
- `backend/app/services/move_plan.py`: `generate_move_plan` — for every
  classified file with a mapped, enabled routing group, computes a
  destination path and runs every Etapa-5/§16 validation, then persists
  one `MoveOperation` row per file plus the `MovePlan` header. Never
  creates a directory, never touches a source file, never computes a
  content hash (hashing is Phase 15's job, run only during an actual
  cross-volume copy).
- `media-organizer destinations --scan-id <id> --config <file.json>` and
  `media-organizer plan --scan-id <id> [--collision-policy] [--validation-mode]`
  CLI commands.
- Unit + integration tests, including the two scenarios the roadmap names
  explicitly: a case-only collision and an over-length destination path,
  both surfaced as plan errors rather than raised exceptions.

### Out (later phases)

- Any code that actually renames, copies, or deletes a file — Phase 15.
- Hash computation (SHA-256, `standard`/`strict` modes) — Phase 15, only
  runs during real cross-volume copies.
- The `is_same_volume(a, b)` helper — explicitly assigned to Phase 15 in
  `specs/tech-stack.md`. Phase 14's disk-space check does not need it (see
  Decisions).
- Explicit user confirmation / approval step (Etapa 6), execution
  progress, cancellation, resume, and the move report — Phase 16.
- `collision_policy` values other than `error` (`rename_with_suffix`,
  `skip`, `deduplicate_by_hash` are explicitly "future" per README §17.5).
- Resolving README §41's open question on country-subfolder naming
  convention (ISO code vs. localized name) — `country_subfolder_enabled`
  is implemented per the README §24.4 model shape, defaulting to
  disabled, using the ISO code already stored on `Classification` (no new
  decision required to ship the field).
- FastAPI/API surface — Stage F.

## Source of truth

- README §16 "Fluxo funcional", Etapa 4 (destination mapping) and Etapa 5
  (move-plan generation and its validation list) — the direct source for
  this phase's checks.
- README §17.1 "Princípios" — "não executar movimentação durante a fase de
  análise" and "não movimentar arquivos cuja origem mudou depois do
  plano" are what Phase 14 must detect and record, not enforce at
  execution time (no executor exists yet).
- README §17.5 "Conflitos de nome" — default `collision_policy: error`,
  never `overwrite`.
- README §24.4 `DestinationRule`, §24.5 `MovePlan`, §24.6 `MoveOperation`
  (= §18 diário transacional) — the persisted shapes.
- README §39, US-003 and its acceptance criteria — the phase's Done-when
  contract.
- `specs/roadmap.md` Phase 14 entry.
- `specs/tech-stack.md` "Cross-platform" table rows tagged "Phase 14":
  case sensitivity, destination-name sanitization, path length.
- `specs/mission.md` principles 1 (local/offline), 2 (read-only until
  Phase 14 — this phase may only read the source tree and write to the
  database), 3 (never destroy data — `collision_policy: error` default).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `models/destination_rule.py`, `models/move_plan.py` (both `MovePlan` and `MoveOperation`), `core/destination_paths.py`, `services/destinations.py`, `services/move_plan.py`, one repository per model | Mirrors the existing `models/`/`repositories/`/`services/` split from Phases 3, 8, 13; `core/destination_paths.py` groups pure path-logic helpers the way `core/ignore_patterns.py` and `core/media_signatures.py` already do. |
| `MoveOperation` created now, not Phase 15 | One journal table, written by Phase 14 (`planned`/`blocked`) and extended by Phase 15 (execution states) | README's own `MoveOperation` "= diário transacional" is the natural persisted shape for a per-file plan line; splitting a separate `MovePlanItem` table now and migrating into `MoveOperation` at Phase 15 would just be a same-shape rename later. |
| Primary key naming | `MoveOperation.id`, not a separate `operation_id` column | Every existing table in this repo (`Scan`, `MediaFile`, `Classification`) already normalizes README's prose field name to a plain `id` int PK; no reason to special-case this table. |
| `MoveOperation.status` at plan time | `"planned"` (clean) or `"blocked"` (a validation check failed; `error_code`/`error_message` hold why) | Phase 15's roadmap entry only enumerates *execution* states (`planned → … → completed/failed/skipped/cancelled`); `"blocked"` is a planning-time-only terminal state distinguishing "will not run without a new plan" from a future execution failure. Documented here since Phase 15/16 will need to recognize it. |
| Disk-space check | Sum `MediaFile.size_bytes` of every file mapped to each destination volume (via `Path(destination_root).drive` on Windows, `os.stat().st_dev` fallback elsewhere) and compare to `shutil.disk_usage(destination_root).free` — required unconditionally, even for a same-volume rename | Same-volume rename doesn't truly consume extra free space, but requiring it anyway is a conservative, cheap safety margin and avoids pulling `is_same_volume` (owned by Phase 15 per tech-stack.md) into this phase just to decide when to skip the check. |
| Destination path shape | `destination_root / [sanitized country subfolder if enabled] / original_file_name` — flat, no source subfolder tree preserved | Matches the README §16 Etapa 4 example (one flat folder per group); `collision_policy: error` means the original name travels unchanged, never auto-renamed. |
| What gets sanitized | Only the generated country-subfolder segment goes through `sanitize_path_component` | `destination_root` is user-supplied and validated for existence/writability directly; the original file name was already valid on the source Windows volume that produced it. The country subfolder is the only path segment this phase constructs from free-text data (`Classification.country_name`/`country_code`), so it's the only one that needs sanitizing. |
| Files without a mapped/enabled `DestinationRule` | Excluded from the plan, counted as `unmapped` in the summary, no `MoveOperation` row created | The roadmap gives the user a mapping *per group*, not a mandatory one; an unmapped group is "leave these alone," not an error. |
| Files without a `Classification` row (scan/extraction errors, `unsupported` kind) | Excluded from the plan, counted as `skipped_unclassified` | Nothing to route them by; matches the Phase 4–13 "record and continue" pattern rather than aborting plan generation. |
| Locked-file detection | Best-effort: attempt to open the source file `"r+b"` and catch `PermissionError`/`OSError` → `SOURCE_LOCKED` | README §16 Etapa 5 lists it explicitly. A real exclusive-lock fixture isn't reliably reproducible cross-machine in a test suite, so the success/failure branches are unit-tested via a monkeypatched `open()` — same documented-gap precedent as Phase 9's RAW rule and Phase 13's DNG thumbnailing. |
| CLI surface | `media-organizer destinations --scan-id <id> --config <file.json>` (JSON: `{routing_group: {"destination_root": ..., "country_subfolder_enabled": bool}}`) then `media-organizer plan --scan-id <id> [--collision-policy error] [--validation-mode standard]` | Two commands matching Etapa 4 and Etapa 5 as separate steps, same `--scan-id`/`--database` shape as `classify`/`report`. A JSON config file scales to N routing groups better than N repeated CLI flags. |
| `MovePlan.status` values | `"draft"` while being built, `"generated"` once `generate_move_plan` returns — regardless of whether individual operations are `blocked` | Plan-level status tracks the *plan's* lifecycle (generated vs. later approved/executed in Phase 16); per-file problems live on `MoveOperation`, not by forking plan-level statuses. |

## Constraints

- **Read-only until Phase 14, and even this phase stays read-only toward
  the source tree** (`specs/mission.md` #2): `generate_move_plan` reads
  source file stats (`exists`, `stat`) and opens files only to probe for
  locks — it never writes, moves, renames, or deletes anything under a
  scanned root, and never creates a destination directory.
- **Never destroy data** (`specs/mission.md` #3): default
  `collision_policy` is `"error"`; `"overwrite"` is never implemented.
- **100% local and offline** (`specs/mission.md` #1): all validation is
  local filesystem/DB work — no network calls.
- **Case-insensitive collisions**: `Foto.jpg` and `foto.jpg` must be
  detected as colliding — both against each other within the plan and
  against files already present at the destination.
- **Portable destination names**: sanitization forbids
  `<>:"/\|?*`, trailing dot/space, and Windows reserved device names.
- **Path length**: every `planned_destination_path` is checked against
  the 260-character Windows limit at plan time, not deferred to
  execution.
- **External tools**: none needed for this phase — no ExifTool/FFmpeg
  call sites.
