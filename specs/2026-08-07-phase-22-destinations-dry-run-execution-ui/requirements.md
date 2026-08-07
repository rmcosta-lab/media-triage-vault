# Requirements — Phase 22: Destinations, dry run, execution UI

## Objective

Close the loop the whole project has been building toward: map
destinations, generate and review a dry-run plan, explicitly approve it,
execute it, and see the final report — all from the browser, using
nothing but the Phase 19 API. This is the last roadmap phase; its done
criterion is README §31's MVP acceptance list in full, exercised end to
end through the UI rather than the CLI.

## Scope

### In

- `frontend/app/plan/page.tsx` (+ a client component behind `<Suspense>`,
  `?scanId=`, matching the Phase 21 `/review` route shape):
  - **Destination mapping form**: one row per routing group present in
    the scan (from the already-fetched analysis report's
    `totals_by_group` — no point asking the user to map a group with
    zero files), each with a destination-folder text field and a
    country-subfolder checkbox. Submits to `PUT
    /api/scans/{scanId}/destinations`.
  - **Plan generation**: a "Generate plan" button calling `POST
    /api/scans/{scanId}/move-plan`; renders the resulting plan summary
    — planned/blocked counts, total bytes, and a table of every blocked
    operation (path, error code, error message) as the "conflicts and
    alerts" README §16 Etapa 6 asks the confirmation screen to show.
  - **Explicit confirmation**: an "Approve plan" button calling `POST
    /api/move-plans/{planId}/approve` — only after this does the UI
    allow execution, mirroring the API's own `approved_at` gate
    (Phase 19) so the UI can't accidentally bypass it.
  - **Execution progress**: an "Execute" button calling `POST
    /api/move-plans/{planId}/execute`, then live progress via the same
    `subscribeJobEvents`/SSE mechanism the dashboard already uses for
    scan/classify jobs (an execute job is a `Job` row like any other,
    Phase 19).
  - **Final move report**: once the execute job reaches a terminal
    state, fetch `GET /api/move-runs/{runId}/report` and render the
    totals (completed/failed/skipped/blocked, bytes moved) plus a table
    of any failed operations with their error.
- `frontend/lib/api.ts`: schemas and calls for `MovePlan`/`MoveOperation`,
  `putDestinations`, `createMovePlan`, `approveMovePlan`,
  `executeMovePlan`, `getMoveRunReport`.
- `frontend/app/review/review-dashboard.tsx`: a "Plan move →" link to
  `/plan?scanId=`, completing the dashboard → review → plan chain.
- A manual, real-browser walkthrough of the complete flow against real
  fixture files, confirming files actually move on disk.

### Out

- Nothing — this is the roadmap's last phase. Any open product question
  (README §41: collision-suffix policy, copy-vs-move, …) stays exactly
  as deferred as it already was; this phase changes no backend behavior,
  only adds the UI for what Phase 19 already built.

## Source of truth

- `specs/roadmap.md` Phase 22 entry — destination mapping form, plan
  summary with conflicts/alerts, explicit confirmation, execution
  progress, final move report; done when the whole MVP flow completes
  from the browser, closing README §31.
- README §16 Etapa 4-8 — destination mapping, plan generation, review,
  confirmation, execution, validation — the functional flow this page
  implements.
- README §31 — the MVP acceptance list this phase's manual walkthrough
  exercises end to end.
- `specs/mission.md` principle 2 — nothing executes without explicit
  confirmation; enforced both by the API (`approved_at` gate, Phase 19)
  and, redundantly and visibly, by the UI only enabling "Execute" after
  "Approve plan" has succeeded.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Route shape | `/plan?scanId=`, same `Suspense`-wrapped `useSearchParams` pattern as `/review` | Consistency with Phase 21; the page is entirely client-fetched, same reasoning as before. |
| Destination form scope | Only routing groups present in the scan (from the analysis report's `totals_by_group`), not the full static `ROUTING_GROUPS` list | Mapping a destination for a group with zero files in this scan is pure noise; the report already tells us exactly which groups matter. |
| Execute progress transport | Reuse `subscribeJobEvents` (Phase 18/20) unmodified | An execute job is a `Job` row exactly like a scan/classify job (Phase 19's own design choice — no separate `MoveRun` entity); no new transport needed. |
| Confirmation enforcement | UI-level gate (disable "Execute" until `approved_at` is set) *in addition to* the API's own `400` | Belt-and-suspenders on the MVP's single non-negotiable safety property (`specs/mission.md` #2); the UI gate is what a real user experiences, the API gate is what actually prevents a bypass. |
| Plan regeneration | Generating a new plan after destinations change is just calling `POST .../move-plan` again — no special "invalidate old plan" UI state | Matches the CLI/API's own model: each `move-plan` call creates a new `MovePlan` row; `GET /api/move-plans/{id}` always reads a specific plan by id, and the UI simply tracks whichever plan id it most recently created. |

## Constraints

- **Explicit confirmation** (`specs/mission.md` #2): the UI never calls
  `execute` before a successful `approve` response.
- **Never destroy data** (`specs/mission.md` #3): unchanged — this phase
  adds no new backend behavior, only surfaces Phase 14-19's existing
  safety guarantees in the browser.
- **Local only**: no new network destination.
