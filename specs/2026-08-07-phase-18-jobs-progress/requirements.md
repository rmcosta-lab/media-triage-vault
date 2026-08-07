# Requirements — Phase 18: Jobs + progress

## Objective

Let the API trigger a scan or a classify run without blocking the HTTP
server, and let a client watch it happen live. This is what makes Stage
G's "launch a scan and watch progress" flow (README §20.1 Passo C)
possible — Phase 17's API was read-only over data the CLI had already
produced; this phase is the first to let the API *do* something,
asynchronously, and report back over Server-Sent Events.

## Scope

### In

- `backend/app/models/job.py`: `Job` table — `job_type` (`scan` |
  `classify`), `scan_id` (nullable — a scan job doesn't know its
  `Scan.id` until the job actually starts), `status` (`queued` |
  `running` | `completed` | `failed` | `cancelled`), `cancel_requested`
  (the external "please stop" signal, separate from `status`),
  `params_json`, `total`/`processed` counters, `message`, `error_code`/
  `error_message`, timestamps.
- `backend/app/repositories/job_repository.py`.
- `backend/app/services/job_runner.py`: a single daemon worker thread
  draining a `queue.Queue` one job at a time (README §26 "limitar
  concorrência"), persisting all state in the `Job` row. No Celery/Redis.
- `should_cancel` hooks added to the four services a job can run —
  `scan_folder` (Phase 4), `detect_media_types_for_scan` (Phase 5),
  `extract_metadata_for_scan` (Phase 6), `classify_scan` (Phase 12) —
  each checked between files/batches only, never mid-file, matching the
  same pattern Phase 15's executor already established for moves.
  `scan_folder` also gains an `on_scan_created` callback so the job
  runner can record `Job.scan_id` as soon as the `Scan` row exists,
  not only once the whole scan finishes.
- API additions (`backend/app/api/routes.py`, `schemas.py`):
  - `POST /api/scans` (body: `{source_root, recursive}`) — queues a scan
    job (scan → media-type detection → metadata extraction, the same
    pipeline the CLI's `scan` command runs), `202` + `JobRead`.
  - `POST /api/scans/{scan_id}/classify` — queues a classify job, `202`
    + `JobRead`.
  - `POST /api/scans/{scan_id}/cancel` — sets `cancel_requested=True` on
    the scan's active job.
  - `GET /api/jobs/{job_id}` — current job state (poll fallback).
  - `GET /api/jobs/{job_id}/events` — SSE stream, one event per state
    change, closing once the job reaches a terminal status.
- Unit tests for the job runner (temp SQLite, no HTTP layer) and the new
  API routes (`TestClient`, including consuming the SSE stream to
  completion); an integration test running a real scan job end to end
  against fixtures via the API.

### Out (later phases)

- Move-plan/execute triggers over HTTP — Phase 19.
- Any UI — Stage G.
- Multi-worker concurrency — README §26 explicitly asks for limited
  concurrency, not a pool; one job at a time is the correct MVP shape.
- Cross-process job durability (a job "in flight" when the process is
  killed stays `running` forever in the DB, never auto-recovered) — the
  same acceptable gap the CLI's `execute`/resume design (Phase 15/16)
  solves differently (idempotent journal, re-run by the user); nothing
  in this phase's done criterion requires surviving a process restart.

## Source of truth

- README §26 "Processamento em background" — local queue, thread/process
  worker, SQLite-persisted state, limited read concurrency, cancellation
  between files, never mid-copy, no Celery/Redis.
- README §25 "Progresso" — `GET /api/jobs/{job_id}/events` via SSE or
  WebSocket (this phase picks SSE, matching `specs/tech-stack.md`).
- README §25 "Scans" — `POST /api/scans`, `POST /api/scans/{scan_id}/cancel`
  (this phase); `GET /api/scans/{scan_id}` and `.../files` already exist
  (Phase 17). A `classify`-triggering route isn't in README's initial
  list but is explicitly named by the roadmap's "POST scan/classify" —
  added as `POST /api/scans/{scan_id}/classify`, the natural analogue.
- `specs/roadmap.md` Phase 18 entry — done when a scan runs via API with
  live progress.
- `specs/tech-stack.md` "Background jobs": simple local queue,
  thread/process + SQLite state, no Celery/Redis; "API layer": SSE for
  progress.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Worker model | One daemon `threading.Thread` draining a `queue.Queue[tuple[Engine, int]]`, started lazily on first submission | README explicitly asks for a thread *or* process, SQLite-persisted state, and limited concurrency — a single worker thread is the simplest shape that satisfies all three without adding a process-management layer. |
| Queue item shape | `(Engine, job_id)`, not bare `job_id` | The API's session dependency (Phase 17) opens a fresh `Engine` per request; tests override it to point at a temp database. Capturing the submitting session's own engine (`session.get_bind()`) and carrying it through the queue means the worker thread always talks to whichever database the request actually used — a bare `job_id` would force the worker to guess a single hardcoded database path, breaking test isolation. |
| Cancellation | `Job.cancel_requested: bool`, separate from `Job.status`; checked via a fresh short-lived `Session` on the shared engine at each service's existing per-item loop boundary | Keeps the "please stop" signal and the "have stopped" fact distinct (a client can poll `cancel_requested=True, status=running` mid-drain), and reuses the exact `should_cancel` pattern Phase 15's executor already proved out rather than inventing a second cancellation mechanism. |
| Which services gained `should_cancel` | All four the job pipeline touches (`scan_folder`, `detect_media_types_for_scan`, `extract_metadata_for_scan`, `classify_scan`) | README §26's cancellation requirement is stated for background processing generally, not just moves; each function already loops per file/batch, so the hook is a small, additive, default-`None` parameter — no existing caller (CLI) changes behavior. |
| `Job.scan_id` timing for a scan job | Populated via a new `on_scan_created` callback fired the instant `scan_folder` creates the `Scan` row (before the file walk even starts), not only once the whole pipeline finishes | Without this, a client would have no `scan_id` to poll/cancel by for the entire — potentially long — duration of a large scan, defeating "live progress." |
| `POST /api/scans/{scan_id}/cancel` before a scan job has a `scan_id` | Not supported (documented gap) — the endpoint looks up the active job by `scan_id`, so a job still `queued` with no `Scan` row yet can't be targeted this way | The window is milliseconds in practice (an idle worker picks up a queued job almost immediately, and `Scan` row creation is `scan_folder`'s very first action); solving it fully would need a second `job_id`-keyed cancel route for a gap this narrow, which isn't worth the extra API surface for the MVP. |
| SSE polling interval | 0.3s, only emitting an event when the serialized `JobRead` payload actually changed | Keeps the stream simple (poll the same `Job` row a `GET` would return) without needing a pub/sub mechanism; 0.3s is responsive enough for human-watched progress without hammering SQLite. |

## Constraints

- **Cancellation never interrupts a file mid-write** (`specs/mission.md`
  #3, README §26): every `should_cancel` check sits at a natural
  per-file/per-batch boundary, never inside a single file's read/write.
- **100% local and offline**: SSE is plain HTTP on `127.0.0.1`; no
  external service, no WebSocket-to-a-third-party.
- **No Celery/Redis**: stdlib `queue`/`threading` only.
- **Read-only toward the source tree**: scan/classify jobs never write
  to a scanned file — unchanged from Phases 4-12, just now reachable
  over HTTP.
