# Requirements — Phase 21: Review UI

## Objective

Give the user a real inventory to review in the browser: every file from
a scan, filterable, with a thumbnail, its classification reasons, and a
way to correct a wrong automatic call — closing the loop README §15.3
opened in Phase 8/12 but the CLI's `override` command was the only way
to reach until now.

## Scope

### In

- Backend: `PATCH /api/files/{file_id}/classification` (body:
  `{routing_group}`) — the one route from README §25's "Classificação"
  group Phase 17 didn't build (that phase was GET-only by design).
  Mirrors the CLI `override` command exactly: validates the routing
  group against `ROUTING_GROUPS`, requires an existing `Classification`
  row (404 otherwise — "run classify first"), sets
  `manual_routing_group`/`effective_routing_group`/`override_timestamp`.
- `frontend/app/review/page.tsx` (+ a client component read via
  `useSearchParams` inside a `Suspense` boundary, `?scanId=`): a
  TanStack Table inventory built from `GET /api/scans/{id}/report`'s
  already-joined `files` array (media + metadata + classification in
  one call — no N+1 per-row fetch).
  - Columns: thumbnail, name, media kind, routing group (with a
    "manual" badge), confidence, country, error.
  - Filters: routing group, a confidence band, "errors only", country —
    applied client-side to the already-fetched array (no new query
    params against the backend; the dataset here is one scan's worth of
    rows, not a paginated multi-scan search).
  - Row selection opens a detail panel: full reasons list, source
    origin/image format, device make/model/software/lens, capture
    time, country name, error code/message — all already present in
    the report row, no extra fetch.
  - The detail panel's routing-group `<select>` is the override editor:
    changing it calls the new `PATCH`, then refetches the report so the
    table/panel reflect the persisted, now-manual value.
- A link from the Phase 20 dashboard ("Review files") to
  `/review?scanId=<id>` once a scan has been classified.
- `@tanstack/react-table` added to `frontend/package.json` (pinned in
  `specs/tech-stack.md` since Phase C planning, first phase to actually
  use it).
- Backend unit tests for the new `PATCH` route; a frontend manual
  browser pass (no test runner configured yet, per Phase 20's
  decision — unchanged this phase).

### Out (later phases)

- Destination mapping, move-plan review/approve/execute UI — Phase 22.
- Server-side/paginated filtering — the roadmap's own phrasing
  ("TanStack Table inventory with filters") describes client-side table
  filtering over one scan's rows, which is what Phase 19's report
  endpoint already returns in one call.

## Source of truth

- `specs/roadmap.md` Phase 21 entry — TanStack Table inventory with
  filters (group, confidence, errors, country), thumbnails, metadata +
  classification reasons panel, manual override editing; done when an
  override made in the UI persists and is marked manual.
- README §25 "Classificação" — `PATCH /api/files/{file_id}/classification`.
- README §15.3 — manual override semantics (`manual_routing_group`
  survives a re-classify; `effective_routing_group` follows the manual
  value once set), already implemented by Phase 12's `classify_scan`
  and the CLI's `override` command; this phase adds the second way to
  reach the same write path.
- `specs/tech-stack.md` "Frontend (Phase C)" — TanStack Table pinned for
  exactly this phase.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Data source for the table | `GET /api/scans/{id}/report` (Phase 19), not `GET /api/scans/{id}/files` + per-file classification/metadata calls | The report endpoint already joins exactly the fields a review table needs into one array; using it avoids an N+1 fetch pattern for what is otherwise a straightforward reuse of existing, tested backend code. |
| Filtering | Client-side, over the already-fetched array | One scan's file count is the MVP's working set (thousands, not millions); the roadmap's own phrase "TanStack Table inventory with filters" describes exactly TanStack's client-side filtering model, not a new paginated search endpoint. |
| Detail panel data | Reused directly from the selected report row — no extra `GET .../metadata` or `.../classification` call | The report row already carries reasons, device fields, and country name; fetching them again would just be a slower path to data already in memory. |
| Route shape | `/review?scanId=` (search param) inside a `Suspense` boundary, not a `/review/[scanId]` dynamic segment | The page is entirely client-fetched (no server-side data loading), so `useSearchParams()` is the documented fit ("Client Components can read search params using the `useSearchParams` hook"); a dynamic segment would only add the async-`params`-in-a-Server-Component ceremony for no benefit here. |
| Override write path | New `PATCH /api/files/{file_id}/classification`, not reusing the CLI's `override` command over some IPC bridge | The API is the UI's only channel to the backend; the route is a direct, thin translation of the already-proven `classification.py`/CLI `override_command` logic (validate group, require existing classification, stamp the three manual fields). |

## Constraints

- **Explainable classification** (`specs/mission.md` #4): the detail
  panel always shows the automatic reasons, even after a manual
  override — nothing is hidden once corrected.
- **Manual overrides recorded separately**: the override endpoint only
  ever writes `manual_routing_group`/`effective_routing_group`/
  `override_timestamp` — `automatic_routing_group` and `confidence` are
  untouched, matching the CLI's `override` command exactly.
- **Coordinates hidden from default output**: unchanged — the report
  payload this phase consumes already excludes GPS fields.
- **Local only**: no new network destination; still only the local API.
