# Validation — Phase 21: Review UI

### Functional

- [x] The review page shows a TanStack Table inventory of a scan's
      files — verified manually with 4 fixtures across 4 groups.
- [x] Filters work: routing group, confidence band, errors-only,
      country — option lists populated correctly from the data
      (`Group`: iphone_photo/mobile_screenshot/video/whatsapp_received;
      `Country`: JP/unknown) in the manual run.
- [x] Each row shows a thumbnail — confirmed visually via screenshot
      (four distinct real thumbnails rendered, not broken images).
- [x] A detail panel shows metadata and classification reasons —
      confirmed manually (source origin, image format, device, reasons
      list all rendered for the selected row).
- [x] Manual override editing works from the UI — changing the
      "Routing group" select called the `PATCH` endpoint and updated
      the row.

### Roadmap done criterion

- [x] An override made in the UI persists (survives reload) and is
      marked manual — manually verified: overrode
      `IMG-20260730-WA0001.jpg` from `whatsapp_received` to `other`, the
      row immediately showed `other` + a "manual" badge, and after a
      full page reload the row still showed `other` + "manual" (fetched
      fresh from the backend, not local state).

### Tests

- [x] Backend: `PATCH /api/files/{id}/classification` covered — happy
      path (`test_patch_file_classification_overrides_and_persists`,
      including a persistence re-read), unknown routing group (`400`,
      `test_patch_file_classification_invalid_group_returns_400`),
      missing classification (`404`,
      `test_patch_file_classification_missing_classification_returns_404`).
- [x] `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` clean.
- [x] `uv run pytest` / `ruff` / `mypy` clean.

### Safety

- [x] The override endpoint only ever writes the three manual fields —
      confirmed by reading `override_file_classification`
      (`automatic_routing_group`/`confidence` never assigned) and by
      the test asserting `automatic_routing_group` is unchanged after
      an override.
- [x] No coordinate-shaped field appears anywhere in the review UI's
      data path — `ScanReportFileSchema` (frontend) and `ReportRow`
      (backend, Phase 13) both omit GPS fields; confirmed by reading
      both.
- [x] No new network destination — `lib/api.ts`'s only additions
      (`overrideClassification`, the report file schema) still go
      through the same `requestJson`/`getBaseUrl()` path as everything
      else.

### Technical

- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean.
- [x] `uv run pytest` green — 290 passed (3 new: PATCH happy path,
      invalid group, missing classification).
- [x] `pnpm exec tsc --noEmit` clean.
- [x] `pnpm lint` clean (fixed a real `react-hooks/set-state-in-effect`
      finding along the way — the initial fetch-on-mount effect called
      `setState` synchronously for the invalid-`scanId` branch; moved to
      a plain derived `invalidScanId` value plus a cancellation-guarded
      `.then()`/`.catch()` fetch, the documented React pattern).
- [x] `pnpm build` succeeds (`/review` included in the build output).

### Manual

- [x] Full browser walkthrough via `playwright-cli`: scanned + classified
      4 fixtures spanning 4 routing groups, opened Review, confirmed
      filter option lists and thumbnails, opened a row's detail panel,
      changed its routing group via the override select, confirmed the
      row updated with a "manual" badge, reloaded the page, and
      confirmed the override was still there — proving it round-tripped
      through the backend rather than only updating local state.

### Note

TanStack Table's installed version (`@tanstack/react-table@9.0.0`)
ships a redesigned API (`useTable`/`tableFeatures`/`createColumnHelper`/
`table.FlexRender`) that differs substantially from the commonly-known
v8 API (`useReactTable`/`getCoreRowModel`/`flexRender`). The package
bundles its own agent-oriented `skills/` docs (`getting-started`,
`core`, `table-features`, `migrate-v8-to-v9`, …) under
`node_modules/@tanstack/*/skills/`, which were read and followed to
implement the table correctly against the actual installed version
rather than a possibly-stale prior version's API.
