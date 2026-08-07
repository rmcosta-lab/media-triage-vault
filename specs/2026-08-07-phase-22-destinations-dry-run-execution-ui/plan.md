# Plan — Phase 22: Destinations, dry run, execution UI

## 1. API client additions

- `frontend/lib/api.ts`:
  - `MoveOperationSchema` (mirrors `MoveOperationRead`), extend into
    `MovePlanSchema` (mirrors `MovePlanRead`: header + `total_planned`/
    `total_blocked`/`total_bytes_planned`/`by_error_code`/`operations`).
  - `MoveReportSchema` — the `GET /api/move-runs/{id}/report` payload
    shape (`totals`, `by_error_code`, `operations` — reuse
    `MoveOperationRowSchema` shaped like the JSON the backend's
    `build_move_report_payload` actually emits, which differs slightly
    from `MoveOperationRead`: snake_case timestamps as ISO strings,
    already the case for both).
  - `putDestinations(scanId, mapping) -> DestinationRule[]` (`PUT`).
  - `createMovePlan(scanId) -> MovePlan` (`POST`, default
    collision_policy/validation_mode).
  - `getMovePlan(planId) -> MovePlan` (`GET`).
  - `approveMovePlan(planId) -> MovePlan` (`POST`).
  - `executeMovePlan(planId) -> Job` (`POST`).
  - `getMoveRunReport(runId) -> MoveReport` (`GET`).

## 2. Plan page

- `frontend/app/plan/page.tsx`: `<Suspense>` wrapper, matching
  `app/review/page.tsx`.
- `frontend/app/plan/plan-dashboard.tsx` (`"use client"`):
  - Reads `scanId` from `useSearchParams()`.
  - Effect (cancellation-guarded, per the Phase 21 lint fix) fetches the
    scan's analysis report on mount for `totals_by_group` — the set of
    routing groups to build destination-folder fields for.
  - Destination form state: `Record<routingGroup, {destinationRoot,
    countrySubfolderEnabled}>`; "Save destinations" submits every group
    with a non-empty `destinationRoot` via `putDestinations`.
  - "Generate plan" calls `createMovePlan`, stores the returned
    `MovePlan` (including `operations`), advances to the "plan"
    stage.
  - Plan summary: `total_planned`, `total_blocked`,
    `total_bytes_planned`; a table of blocked operations
    (`planned_destination_path`, `error_code`, `error_message`) — the
    conflicts/alerts view.
  - "Approve plan" calls `approveMovePlan`; disabled once already
    approved. "Execute" is disabled until `approved_at` is set.
  - "Execute" calls `executeMovePlan`, stores the returned `Job`,
    subscribes via `subscribeJobEvents` (unmodified from Phase 18/20)
    for live status/processed count.
  - On a terminal job status, fetches `getMoveRunReport` and renders
    `totals` (completed/failed/skipped/blocked, bytes moved) plus a
    table of failed operations (path, error).
- `frontend/app/review/review-dashboard.tsx`: add a "Plan move →" link
  to `/plan?scanId={scanId}` (the `scanId` is already in scope from the
  page's own search param).

## 3. Verification

- `pnpm exec tsc --noEmit`, `pnpm lint`, `pnpm build`.
- `uv run pytest` / `ruff` / `mypy` (no backend changes expected, but
  re-run to confirm nothing regressed).
- Manual, in a real browser via `playwright-cli`, against a real
  fixture copy: scan → classify → review (confirm the "Plan move" link)
  → map destinations for every present group → generate plan → confirm
  the summary matches expectations (planned/blocked/bytes) → approve →
  confirm "Execute" was disabled before approval and enabled after →
  execute → watch live progress → confirm the final move report → verify
  on disk that files actually moved and the source directory emptied
  out — the full README §31 MVP flow from the browser.

## 4. Verification checklist (README §31, exercised by the manual walkthrough)

1. Recursive scan — Phase 4/20.
2. Media type identification — Phase 5.
3. iPhone identification — Phase 9.
4. iPhone RAW separation — Phase 9.
5. WhatsApp identification — Phase 10.
6. Screenshot identification with confidence — Phase 10.
7. Offline country resolution — Phase 11.
8. Local HTML report — Phase 13 (not re-verified here; unchanged).
9. Review and override — Phase 21.
10. Destination configuration — **this phase**.
11. Dry-run generation — **this phase** (plan summary before execute).
12. Overwrite blocking — Phase 14/15 (`DESTINATION_EXISTS`/`NAME_COLLISION`),
    surfaced in this phase's blocked-operations table.
13. Transactional-journal move — Phase 15, triggered from **this phase**.
14. Size/hash validation per mode — Phase 15.
15. Error report — **this phase**'s final move report.
16. Resume an interrupted run — Phase 16/18 (job resumability); not
    re-tested here (already covered by Phase 16's kill-and-resume test
    and Phase 18's job-runner tests).
17. Integration tests passing — `uv run pytest`, full suite, green.
