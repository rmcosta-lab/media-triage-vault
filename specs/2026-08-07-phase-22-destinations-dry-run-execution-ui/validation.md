# Validation — Phase 22: Destinations, dry run, execution UI

### Functional

- [x] Destination mapping form works, scoped to groups present in the
      scan — manual run: form showed exactly the 4 groups present
      (iphone_photo, mobile_screenshot, video, whatsapp_received), no
      others.
- [x] Plan generation shows a summary with planned/blocked counts, total
      bytes, and a conflicts/alerts table of blocked operations —
      manual run: `Planned=4, Blocked=0, Total bytes=3599` (no conflicts
      table rendered since nothing was blocked — verified the
      conditional render is correct by reading the component).
- [x] Execution requires explicit approval — "Execute" was `disabled`
      immediately after plan generation, and became enabled only after
      "Approve plan" succeeded (both observed directly in the
      accessibility snapshot during the manual run).
- [x] Execution progress is shown live — `Status: completed, Files
      processed: 4` rendered via the same SSE mechanism as scan/classify.
- [x] A final move report is shown after execution — `Completed: 4,
      Failed: 0, Skipped: 0, Bytes moved: 3599`.

### Roadmap done criterion

- [x] The whole MVP flow completes from the browser (README §31) —
      full manual walkthrough: scan → classify → review → plan move →
      map 4 destinations → generate plan → confirm Execute disabled
      pre-approval → approve → execute → live progress → move report →
      **verified on disk**: all 4 fixture files present at their correct
      group destination folders with the source directory completely
      empty afterward.

### Tests

- [x] `pnpm exec tsc --noEmit` / `pnpm lint` / `pnpm build` clean
      (`/plan` included in the build output).
- [x] `uv run pytest` (290 passed) / `ruff` / `mypy` clean — no backend
      behavior changed this phase, confirmed no regression.

### Safety

- [x] The UI never calls `execute` before a successful `approve` call —
      confirmed by reading `plan-dashboard.tsx` (`disabled={!plan.approved_at
      || !!executeJob}`) and directly observed in the manual run (button
      was disabled, then enabled only post-approval).
- [x] No new network destination — `lib/api.ts`'s new functions all go
      through the existing `requestJson`/`getBaseUrl()` path.

### Technical

- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean.
- [x] `uv run pytest` green — 290 passed (unchanged from Phase 21; no
      backend code touched).
- [x] `pnpm exec tsc --noEmit` clean.
- [x] `pnpm lint` clean.
- [x] `pnpm build` succeeds.

### Manual

- [x] Full browser walkthrough via `playwright-cli` against 4 real
      fixture files spanning 4 routing groups: scan → classify → review
      → "Plan move →" → destination form (correctly scoped to the 4
      present groups) → filled all 4 destination paths → "Save
      destinations" → "Generate plan" (4 planned/0 blocked/3599 bytes)
      → confirmed "Execute" disabled → "Approve plan" (button became
      "Approved", disabled) → "Execute" became enabled → clicked it →
      live progress reached `completed`/`4` processed → move report
      showed `4` completed/`0` failed/`0` skipped/`3599` bytes moved →
      confirmed on disk: all 4 files present under their correct
      `dest/<group>/` folder, source directory empty. Zero console
      errors throughout. Runtime database temporarily swapped for the
      manual run and restored afterward.

This closes the roadmap: all 22 phases complete, the full US-001→US-004
flow works both from the CLI and from the browser.
