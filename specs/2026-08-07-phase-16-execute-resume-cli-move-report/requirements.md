# Requirements — Phase 16: Execute/resume CLI + move report

## Objective

Expose Phase 15's `execute_move_plan` through the CLI as `media-organizer
execute`, closing US-004 and Stage E: an explicit confirmation step before
anything runs, live per-file progress, graceful cancellation between
files (not mid-operation), resuming an interrupted run by simply
re-invoking the same command (the journal already makes this safe), and a
final move report. This is the last phase before the source engine's
read/analyze/move flow is complete end to end from the terminal.

## Scope

### In

- `backend/app/services/move_report.py`: `generate_move_report(session,
  move_plan_id, output_dir, execution_summary, elapsed_seconds) ->
  MoveReportSummary` — writes `move_report.json` (full detail, README
  §19.3 fields) and `move_report.csv` (one row per operation) to
  `output_dir`.
- `media-organizer execute --scan-id <id> --output <dir> [--confirm]
  [--validation-mode]` CLI command:
  - Without `--confirm`: prints the Etapa 6 confirmation summary (file
    count, total bytes, blocked count, already-finished count from a
    prior run) and exits without touching anything.
  - With `--confirm`: runs `execute_move_plan` against the scan's latest
    `MovePlan`, printing per-file progress, installs a `SIGINT` handler
    that requests cancellation between files (not mid-copy) rather than
    raising `KeyboardInterrupt` inside a write, then writes the move
    report.
- Unit test for `move_report.py` and an integration test covering the
  full `scan → classify → destinations → plan → execute` pipeline over
  fixtures, plus a kill-and-resume scenario: execute stops partway
  (simulated via `should_cancel`), then a second `execute` call finishes
  the remaining files.
- One additional `execute_move_plan` unit test (Phase 15's module):
  `should_cancel` returning `True` stops the loop before the next
  `planned` operation, leaving it untouched for a later resume — the
  service-level behavior this phase's CLI cancellation depends on, not
  exercised by Phase 15's own test suite.

### Out (later phases)

- FastAPI/API surface, SSE progress — Stage F.
- Any UI — Stage G.
- `collision_policy` values other than `error` — unchanged from Phase 14.
- A real interactive Ctrl+C test — SIGINT delivery is not reliably
  scriptable cross-platform in an automated `pytest` run; the wiring
  (`should_cancel` callable stops the loop) is unit-tested, real Ctrl+C
  behavior is a manual check.

## Source of truth

- README §16 "Fluxo funcional" Etapa 6 (confirmation), Etapa 7
  (execution), Etapa 8 (validation + final report).
- README §19.3 "Relatório de movimentação" — the move-report field list.
- README §40, US-004 and its acceptance criteria — this phase's
  Done-when contract: requires confirmation, records each operation,
  never overwrites, validates files, allows resume, shows progress,
  records failures, generates a final report.
- `specs/roadmap.md` Phase 16 entry.
- `specs/mission.md` principle 2 (explicit approval before execution)
  and principle 3 (never destroy data, resumable, idempotent — inherited
  from Phase 15, surfaced here).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Confirmation mechanism | An explicit `--confirm` boolean flag, not an interactive `y/N` prompt | Every other command in this CLI (`plan`, `destinations`) is fully non-interactive and scriptable/testable via `CliRunner`; a `typer.confirm` prompt would block in a non-TTY test run. Omitting `--confirm` still prints the full Etapa 6 summary, so the user sees exactly what would happen before re-running with it. |
| Cancellation mechanism | `signal.signal(signal.SIGINT, handler)` sets a flag instead of raising `KeyboardInterrupt`; `execute_move_plan`'s existing `should_cancel` hook (Phase 15) polls that flag between operations | A raw `KeyboardInterrupt` could land mid-copy or mid-rename; deferring to the next `should_cancel()` check (already only evaluated between operations in Phase 15's loop) guarantees cancellation never interrupts a single file's write sequence. |
| Resume | No separate `resume` command — re-running `execute --confirm` on the same scan resolves the same latest `MovePlan` and calls `execute_move_plan` again, which is already idempotent (Phase 15) | A dedicated resume command would just be `execute` with extra ceremony; the journal, not the CLI, is what makes re-running safe. |
| Move plan selection | Always `MovePlanRepository.get_latest_for_scan(scan_id)` — no `--move-plan-id` option | Matches `plan`'s own "one active plan per scan" mental model from Phase 14; a scan is re-planned (not multi-planned) between attempts. |
| Report formats | JSON (full detail, machine-readable) + CSV (one row per operation, spreadsheet-friendly) — no HTML | README §19.3 lists required *content*, not a format; Phase 13's analysis report already owns the HTML/browser experience (Phase 22 will surface execution in the browser), so there's no reader for a standalone move-report HTML yet. |
| `--validation-mode` override | Optional CLI flag; defaults to the plan's own `validation_mode` if omitted | Lets a user upgrade to `strict` at execution time without regenerating the plan, while keeping `standard` (set at `plan` time) as the default path. |

## Constraints

- **Explicit confirmation** (`specs/mission.md` #2): `execute_move_plan`
  is never called without `--confirm` on the command line.
- **Never destroy data** (`specs/mission.md` #3): inherited from Phase
  15 — no change to the executor's safety behavior, only surfaced via
  CLI and the report.
- **100% local and offline**: no network calls; report files are local.
- **Idempotent and resumable**: re-running `execute` on a plan that is
  partially or fully done performs no duplicate work (already guaranteed
  by Phase 15, verified again here through the CLI).
