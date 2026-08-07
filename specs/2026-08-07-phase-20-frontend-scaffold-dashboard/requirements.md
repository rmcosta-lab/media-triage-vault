# Requirements — Phase 20: Frontend scaffold + dashboard

## Objective

Stand up the Next.js app (README §20.1 Passo C) and prove the full
"launch a scan, watch it live, see a summary" loop from a real browser
against the Phase 17-19 API. This is Stage G's opening phase — the core
engine and API are done; everything from here on is interface work on
top of them.

## Scope

### In

- `frontend/`: Next.js (App Router) + TypeScript + pnpm, per
  `specs/tech-stack.md`.
- A typed API client (`lib/api.ts`) with Zod schemas validating every
  response shape the dashboard consumes (`Scan`, `Job`), against the
  Phase 17-19 backend contract.
- One dashboard page (`app/page.tsx`):
  - A scan-launch form: an absolute-path text field + a "recursive"
    checkbox + submit. Validation is backend-driven — the form submits
    to `POST /api/scans` and surfaces the API's own `400` message
    (invalid/missing path) rather than re-implementing path validation
    in the browser.
  - A live progress view for the resulting job, subscribed via the
    browser's native `EventSource` to `GET /api/jobs/{job_id}/events`
    (SSE, Phase 18) — shows status and processed count as they change,
    switching to a summary once the job reaches a terminal state.
  - Once the scan completes: a "Classify" button (`POST
    /api/scans/{scan_id}/classify`) reusing the same live-progress
    pattern, and a group-totals dashboard (`GET /api/scans/{scan_id}/report`,
    Phase 19) — a simple count-per-routing-group summary. Classify is
    included because the roadmap's "group totals dashboard" is only
    meaningful once something is classified; nothing here duplicates
    Phase 21's full review table.
- The backend's CORS/network posture is unchanged: the frontend talks
  only to `http://127.0.0.1:<port>` (configurable via an env var,
  defaulting to the `media-organizer serve` default port), never a
  remote host.
- Minimal styling (plain CSS, no component/design library — none is
  pinned in `specs/tech-stack.md` for this phase).

### Out (later phases)

- TanStack Table inventory, filters, thumbnails, override editing —
  Phase 21.
- Destination mapping form, plan review/approve/execute UI — Phase 22.
- Any design system beyond "readable and functional" — nothing in the
  roadmap or tech-stack pins one yet.
- Playwright E2E — `specs/tech-stack.md` lists it for "once the frontend
  exists," not this phase's own done criterion.

## Source of truth

- README §20.1 Passo C — "acompanhar progresso" is this phase's first
  UI capability.
- `specs/roadmap.md` Phase 20 entry — Next.js/TypeScript/pnpm; scan
  launch form (path field, backend-validated); progress view via SSE;
  group totals dashboard; done when a scan can be started and watched
  from the browser.
- `specs/tech-stack.md` "Frontend (Phase C)" — Next.js, TypeScript,
  React, TanStack Table (Phase 21), Zod, pnpm with lockfile.
- `specs/mission.md` principle 1 — the frontend is still a local,
  offline artifact; it talks only to the local API, never a remote
  service, and ships no analytics/telemetry/CDN dependency it can avoid.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework setup | `pnpm create next-app` (App Router, TypeScript, no Tailwind) inside `frontend/` | Matches `specs/tech-stack.md` exactly; App Router is the current Next.js default and plays well with the simple single-dashboard-page scope here. |
| Backend base URL | `NEXT_PUBLIC_API_BASE_URL` env var, default `http://127.0.0.1:8000` | Matches `media-organizer serve`'s default port (Phase 17); keeping it an env var (not hardcoded) lets a real user point at a different port without a rebuild, while the default keeps local dev friction-free. |
| Progress transport | Browser-native `EventSource` against `GET /api/jobs/{job_id}/events` | Phase 18 already serves SSE; `EventSource` needs no extra dependency and is the standard client for exactly this. |
| Response validation | Zod schemas mirroring the Phase 17-19 Pydantic response shapes, parsed at the API-client boundary | Pinned in `specs/tech-stack.md`; catches a client/server shape drift at the fetch call site instead of an obscure render-time crash. |
| Scope of the "dashboard" | Scan summary + a Classify trigger + totals-by-group from the analysis report | Roadmap explicitly asks for "group totals," which only exist post-classification; going further (a full file table) is Phase 21's named scope. |
| Styling | Plain CSS modules, no UI/component library | Nothing pinned in `specs/tech-stack.md`; adding one now would be an unrecorded dependency decision this phase has no mandate to make. |

## Constraints

- **Local only** (`specs/mission.md` #1): the frontend never calls
  anything but the local API; no analytics, telemetry, or CDN-hosted
  script/font/stylesheet.
- **Backend-driven validation**: the scan-launch form does not
  reimplement path-existence checking client-side — it trusts and
  surfaces the API's own `400`.
- **Read the API as contracted**: every field the dashboard reads is
  validated against a Zod schema, not accessed as untyped JSON.
