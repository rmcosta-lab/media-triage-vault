# Plan — Phase 20: Frontend scaffold + dashboard

## 1. Scaffold

- `pnpm create next-app frontend --typescript --app --no-tailwind
  --eslint --use-pnpm` (App Router, no Tailwind — nothing pinned in
  `specs/tech-stack.md` for a component/CSS framework).
- `pnpm add zod` in `frontend/`.
- Remove `next/font/google` from `app/layout.tsx` (avoids a build-time
  fetch to Google's font CDN; `globals.css` already uses a system font
  stack) and the unused default `public/*.svg` assets.
- `frontend/README.md`: replace the generic create-next-app boilerplate
  with actual run instructions (`pnpm dev`, backend prerequisite,
  `NEXT_PUBLIC_API_BASE_URL`).
- `frontend/.env.local.example` documenting `NEXT_PUBLIC_API_BASE_URL`
  (defaults to `http://127.0.0.1:8000`, matching `media-organizer
  serve`'s default port).

## 2. Backend fix: CORS

- Manual browser testing immediately surfaced a real bug: the browser's
  `fetch`/`EventSource` calls from `http://localhost:3000` to
  `http://127.0.0.1:8000` are blocked by CORS (no
  `Access-Control-Allow-Origin` header), since FastAPI has no CORS
  middleware configured. `backend/app/api/app.py`: add
  `CORSMiddleware` with `allow_origin_regex=r"^http://(localhost|
  127\.0\.0\.1)(:\d+)?$"` — any local port, never a non-loopback origin.
  New tests: `test_cors_allows_local_frontend_origin`,
  `test_cors_rejects_non_local_origin` (`test_api_routes.py`).

## 3. Typed API client

- `frontend/lib/api.ts`: Zod schemas (`Scan`, `Job`) mirroring the
  Phase 17-19 Pydantic response shapes; `ApiError` (message + HTTP
  status); `requestJson` helper that parses every response through its
  schema and raises `ApiError` with the backend's own `detail` message
  on a non-2xx response; `startScan`, `startClassify`, `getJob`,
  `getScan`, `getScanReport`; `subscribeJobEvents(jobId, onEvent)`
  wrapping the browser's native `EventSource` against `GET
  /api/jobs/{job_id}/events`, returning an unsubscribe function.

## 4. Dashboard page

- `frontend/app/page.tsx` (`"use client"`): a small state machine
  (`idle → scanning → scanned → classifying → classified`) driving:
  - A scan-launch form (path text field + recursive checkbox); submits
    to `startScan`, surfaces a thrown `ApiError`'s message inline
    (backend-driven validation, no client-side path checking).
  - A live "Scan progress" panel subscribed via `subscribeJobEvents`,
    unsubscribing on a terminal status.
  - Once `completed`: fetch the `Scan` row for a summary panel
    (total files/bytes) and reveal a "Classify" button.
  - Classify reuses the exact same watch-job pattern.
  - Once classification completes: fetch the scan report and render
    `totals_by_group` as a simple list — the "group totals dashboard."
- `frontend/app/page.module.css`: plain CSS Modules (all selectors
  scoped under a local class — Turbopack's CSS-modules transform
  rejects a bare-element selector like `button` as "not pure").

## 5. Verification

- `pnpm exec tsc --noEmit`
- `pnpm lint`
- `pnpm build`
- Manual, in a real browser via the `playwright-cli` skill: started
  `media-organizer serve` and `pnpm dev` against a temp fixture
  directory; drove the full flow — fill path, start scan, watch live
  SSE progress update in the DOM, see the scan summary, click Classify,
  watch that complete, see the group-totals list render
  (`whatsapp_received: 1`, `iphone_photo: 1` for two fixtures) — with
  zero console errors after the CORS fix. Also verified the error path:
  an invalid path surfaces the backend's exact `400` message inline.
- `uv run pytest` / `ruff` / `mypy` re-run on the backend after the CORS
  middleware addition — all green, no regression.
