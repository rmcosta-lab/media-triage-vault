# Requirements — Phase 19: Plan/execute API

## Objective

Close the loop US-001→US-004 opened over HTTP: map destinations, generate
a move plan, review it, approve it, execute it, watch it, and read the
final report — all through the API, mirroring what the CLI's
`destinations`/`plan`/`execute` commands already do locally. This is the
last backend phase; Stage G's UI (Phase 20-22) has nothing left to wait
on after this one.

## Scope

### In

- `PUT /api/scans/{scan_id}/destinations` — same mapping shape as the
  CLI's `--config` JSON, synchronous (same cost as `destinations`).
- `POST /api/scans/{scan_id}/move-plan` — generates a dry-run plan,
  synchronous (same cost as `plan`). Returns the plan plus every
  `MoveOperation` it produced.
- `GET /api/move-plans/{plan_id}` — plan header, summary counts, and the
  full operation list (what Phase 22's review screen renders).
- `POST /api/move-plans/{plan_id}/approve` — the API's explicit
  confirmation step (README §16 Etapa 6), stamping `MovePlan.approved_at`
  (a Phase 14 field, unused until now).
- `POST /api/move-plans/{plan_id}/execute` — queues a background
  `job_type="execute"` job (extends Phase 18's runner) that calls
  Phase 15's `execute_move_plan`; refuses (`400`) an unapproved plan.
  The `Job.id` returned *is* README §25's "move run" id.
- `GET /api/move-runs/{run_id}`, `POST /api/move-runs/{run_id}/cancel` —
  thin wrappers over the `Job` resource, scoped to `job_type="execute"`.
- `GET /api/move-runs/{run_id}/report` — the move report (Phase 16's
  content), computed on demand from persisted `MoveOperation` rows, no
  file written to disk.
- `GET /api/scans/{scan_id}/report` — the analysis report's JSON shape
  (Phase 13's `report.json` content), computed on demand, no thumbnails
  generated (the API already has its own on-demand thumbnail endpoint,
  Phase 17) and nothing written to disk.
- Refactor `services/move_report.py` and `services/reports.py` to derive
  their payload purely from persisted rows (no live "just ran this"
  object required), so the same builder serves both the CLI's
  file-writing commands and the API's on-demand routes.
- Unit tests for every new route (happy path + error cases) and an
  integration test running the complete flow — scan → classify →
  destinations → move-plan → approve → execute → report — entirely over
  HTTP.

### Out (later phases)

- Any UI — Stage G.
- SSE progress for an execute job specifically — already covered
  generically by Phase 18's `GET /api/jobs/{job_id}/events` (an execute
  job is a `Job` like any other; `/move-runs/{run_id}` is a scoped read,
  not a second progress mechanism).
- `collision_policy` values other than `error` — unchanged since Phase 14.

## Source of truth

- README §25 "Destinos e plano" / "Execução" / "Relatórios" route lists.
- README §16 Etapa 4-8 — the destination mapping → plan → confirm →
  execute → validate → report sequence this phase exposes over HTTP.
- `specs/roadmap.md` Phase 19 entry — done when the full US-001→US-004
  flow works over HTTP.
- `specs/mission.md` principle 2 — nothing executes without explicit
  confirmation; the `approved_at` gate on `execute` is this phase's
  enforcement of that at the API layer (the CLI's `--confirm` flag was
  Phase 16's equivalent for a single synchronous command).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| "Move run" identity | An `execute` `Job`'s own `id` *is* the run id — no separate `MoveRun` table | README's data model (§24) never defines a `MoveRun` entity, only `MovePlan`/`MoveOperation`; a `Job` row already carries exactly the state (`status`, progress, timestamps, cancel flag) a "run" needs, and reusing Phase 18's runner avoids a second, parallel async-work mechanism. |
| Approval gate | `POST .../execute` returns `400` unless `MovePlan.approved_at` is set | Makes "nothing moves without explicit confirmation" (`specs/mission.md` #2) structurally true at the API boundary, not just a UI convention — a client can't skip straight from plan to execute. |
| `move-plan`/`destinations` stay synchronous | Not queued as background jobs | Same cost profile as the CLI's `destinations`/`plan` commands, which also run synchronously; roadmap Phase 18 only names "scan/classify" for the job treatment, and plan generation doesn't touch the filesystem beyond stats, so it doesn't share execute's long-I/O profile. |
| Report payload refactor | `move_report.py`/`reports.py` payload builders no longer take a live summary object — they recompute totals directly from persisted rows | The CLI already persists everything before printing a summary; deriving the report purely from the database means the exact same function serves an on-demand API read (`GET .../report`) called anytime after the fact, with zero duplicated computation and zero behavior change for the CLI (verified: existing Phase 16 tests pass unchanged). |
| Report response shape | Plain `dict` return (no `response_model`), FastAPI's default JSON encoding | Both payloads are already-nested plain-dict/dataclass structures (Phase 13/16's own file-writing code serializes the identical shape); wrapping them in another Pydantic schema would just be a second definition of the same shape for no behavioral benefit. |

## Constraints

- **Explicit confirmation** (`specs/mission.md` #2): enforced by the
  `approved_at` gate described above.
- **Never destroy data** (`specs/mission.md` #3): unchanged — execution
  still goes through Phase 15's journal.
- **Coordinates hidden from default output**: `GET .../report` reuses
  `ReportRow`, which already excludes GPS fields (Phase 13).
- **100% local and offline**: no network calls; report generation reads
  only the local database.
