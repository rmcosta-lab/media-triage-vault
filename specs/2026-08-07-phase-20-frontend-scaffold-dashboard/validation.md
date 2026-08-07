# Validation — Phase 20: Frontend scaffold + dashboard

### Functional

- [x] Next.js + TypeScript + pnpm scaffold exists under `frontend/`.
- [x] A scan can be launched from a form (path field + recursive
      checkbox), validated by the backend (invalid path surfaces the
      API's own `400` message, not a client-side check).
- [x] Progress is shown live via SSE (`EventSource` against `GET
      /api/jobs/{job_id}/events`).
- [x] A group-totals dashboard renders after classification.

### Roadmap done criterion

- [x] A scan can be started and watched from the browser — verified in
      a real browser (Chromium via `playwright-cli`): filled the path,
      clicked "Start scan," watched `status`/`processed`/`message`
      update live without a page reload, saw the scan summary, clicked
      "Classify," watched that complete, saw the group-totals list.

### Tests

- [x] `pnpm exec tsc --noEmit` — no type errors.
- [x] `pnpm lint` — clean.
- [x] `pnpm build` — production build succeeds.
- [x] Backend: `test_cors_allows_local_frontend_origin` /
      `test_cors_rejects_non_local_origin` cover the new CORS
      middleware; full `uv run pytest` (285 + 2 = 287... see Technical)
      still green after the change.

### Safety

- [x] The frontend talks only to the local API — confirmed by reading
      `lib/api.ts` (the only network calls are `fetch`/`EventSource`
      against `NEXT_PUBLIC_API_BASE_URL`, defaulting to
      `http://127.0.0.1:8000`).
- [x] No CDN asset is loaded — `next/font/google` removed; no external
      script/stylesheet/font anywhere in `app/`.
- [x] CORS is scoped to loopback origins only — `allow_origin_regex`
      matches `localhost`/`127.0.0.1` on any port and nothing else;
      `test_cors_rejects_non_local_origin` proves a non-local `Origin`
      gets no `Access-Control-Allow-Origin` header.
- [x] The backend still binds only `127.0.0.1` — unchanged from Phase
      17/18/19; confirmed again via `netstat` during the manual run.

### Technical

- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean.
- [x] `uv run pytest` green — 287 passed (2 new: CORS allow/reject).

### Manual

- [x] Full browser walkthrough via `playwright-cli` against a real
      `media-organizer serve` + `pnpm dev`: scan → live progress →
      summary → classify → live progress → group totals
      (`whatsapp_received: 1`, `iphone_photo: 1` for the two fixtures
      used), zero console errors; invalid-path error path confirmed
      showing the backend's exact message. This is also what caught the
      CORS bug fixed in this phase (see `plan.md` §2) — without it, the
      scan-launch form would have silently failed in every real browser
      while looking correct in code review.
