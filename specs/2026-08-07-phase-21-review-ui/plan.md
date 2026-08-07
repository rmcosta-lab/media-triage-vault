# Plan — Phase 21: Review UI

## 1. Backend: override endpoint

- `backend/app/api/schemas.py`: `ClassificationOverrideRequest
  {routing_group: str}`.
- `backend/app/api/routes.py`: `PATCH /files/{file_id}/classification`
  — `404` if no `Classification` row exists for `file_id`; `400` if
  `routing_group not in ROUTING_GROUPS`; otherwise set
  `manual_routing_group`/`effective_routing_group`/
  `override_timestamp = datetime.now(UTC)`, persist, return
  `ClassificationRead`.
- `backend/tests/unit/test_api_routes.py`: happy path (persists,
  `manual_routing_group` set, response reflects it), unknown routing
  group (`400`), missing classification (`404`).

## 2. Frontend dependency

- `pnpm add @tanstack/react-table` in `frontend/`.

## 3. API client additions

- `frontend/lib/api.ts`: `ScanReportFileSchema` (the report's `files[]`
  row shape — media/metadata/classification fields, no coordinates),
  extend `ScanReportSchema` with `files: ScanReportFileSchema[]`;
  `overrideClassification(fileId, routingGroup) -> Classification`
  (`PATCH`); a `ROUTING_GROUPS` constant mirroring the backend's list
  (needed for the override `<select>`'s options — small, stable, and
  not worth a round trip to fetch).

## 4. Review page

- `frontend/app/review/page.tsx`: default export wraps a client
  component in `<Suspense>` (required for `useSearchParams`).
- `frontend/app/review/review-dashboard.tsx` (`"use client"`):
  - Reads `scanId` from `useSearchParams()`; a plain derived
    `invalidScanId` boolean (not state) covers the missing/NaN case.
  - Fetches `GET /api/scans/{scanId}/report` in a `useEffect` keyed on
    `[scanId, invalidScanId, refetchToken]`; `setState` only happens
    inside the fetch promise's `.then()`/`.catch()`, guarded by a
    `cancelled` flag set in the effect's cleanup — `eslint-plugin-react-hooks`'s
    `set-state-in-effect` rule rejects a synchronous `setState` call
    reachable directly from the effect body, which an earlier draft
    (an early-return `setError(...)` for an invalid `scanId`, before any
    `await`) tripped. An override bumps `refetchToken` to re-run the
    same effect rather than calling a separately-invoked fetch function.
  - Filter state: `groupFilter`, `confidenceFilter` (`all` | `high`
    ≥0.85 | `medium` 0.60-0.85 | `low` <0.60), `errorsOnly: boolean`,
    `countryFilter`; group/country option lists derived from the
    fetched rows (`Set` of distinct values).
  - Filters applied via `Array.prototype.filter` before handing rows to
    the table — no TanStack filter feature registered.
  - TanStack Table v9's actual installed API (see `specs/tech-stack.md`
    "Frontend"): module-scope `tableFeatures({})` and
    `createColumnHelper<typeof features, ScanReportFile>()`; columns
    built with `columnHelper.accessor(...)`/`columnHelper.display(...)`;
    `useTable({ features, data: filteredFiles, columns })`; rendered via
    `table.getHeaderGroups()`/`table.getRowModel().rows`/
    `row.getAllCells()` and `<table.FlexRender header={...}>`/
    `<table.FlexRender cell={...}>` (the table-instance-bound renderer,
    not a standalone `flexRender` function).
  - Columns: thumbnail (`<img src="{API_BASE}/api/files/{id}/thumbnail">`,
    lazy-loaded), file name, media kind, routing group (+ a "manual"
    badge when `manual_override`), confidence (formatted `%`), country,
    error (code or "—").
  - Row click sets `selectedFileId`; a side panel renders the matching
    row's full detail (reasons list, source origin/image format,
    device fields, capture time, error message) plus a routing-group
    `<select>` defaulting to the row's current group.
  - Changing the `<select>` calls `overrideClassification`, then bumps
    `refetchToken` (keeps the table, filters, and panel all consistent
    with the persisted state in one code path rather than hand-patching
    local state).
- `frontend/app/page.tsx`: after classification completes, a "Review
  files →" link to `/review?scanId={scan.id}` (`next/link`).

## 5. Verification

- `pnpm exec tsc --noEmit`, `pnpm lint`, `pnpm build`.
- `uv run pytest` / `ruff` / `mypy` for the backend addition.
- Manual, in a real browser via `playwright-cli`: scan + classify a
  small real fixture set (already covers multiple routing groups),
  open Review, confirm thumbnails render, apply each filter kind, open
  a row's detail panel, change its routing group, confirm the row
  updates with a "manual" badge and the new group — then reload the
  page and confirm the change persisted (proves it round-tripped
  through the backend, not just local state).
