# Requirements — Phase 17: FastAPI read layer

## Objective

Expose the data every prior CLI phase already produces (scans, files,
classifications, metadata, thumbnails) over a local-only HTTP API, so
Stage G's Next.js UI has something to read from. This is Stage F's
opening phase and stays strictly read-only: no scan/classify/plan/execute
trigger exists yet (Phase 18 adds the background job runner those need;
Phase 19 adds the write endpoints). Nothing here writes to the source
tree or the database beyond the on-demand thumbnail cache this phase
introduces.

## Scope

### In

- New `fastapi`/`uvicorn` dependencies (`pyproject.toml`), `httpx` as a
  dev dependency (required by FastAPI's `TestClient`).
- `backend/app/api/schemas.py`: read-only Pydantic response models —
  `ScanRead`, `MediaFileRead`, `ClassificationRead`, `MediaMetadataRead`
  — each built with `from_attributes=True` so a route can return a
  SQLModel row directly. `ClassificationRead`/`MediaMetadataRead`
  deliberately omit `gps_latitude`/`gps_longitude` (and
  `MediaMetadataRead` also omits `gps_position_raw`/
  `location_information`) — the same coordinate exclusion the CLI's
  `inventory.json` already applies (README §14.4/§28), now enforced at
  the API boundary too.
- `backend/app/api/deps.py`: `get_session_dependency` — a FastAPI
  dependency yielding a `Session` against the standard database path
  (or an overridden engine in tests via `app.dependency_overrides`).
- `backend/app/api/routes.py`: the five GET endpoints below.
- `backend/app/api/app.py`: `create_app() -> FastAPI` — binds no host
  itself (that's `uvicorn`'s job at serve time) but disables the
  default interactive docs (see Decisions).
- `media-organizer serve [--port 8000]` CLI command — the only way to
  start the API; always binds `127.0.0.1`, never configurable to
  another host.
- Endpoints (all GET, all read-only):
  - `GET /api/scans/{scan_id}`
  - `GET /api/scans/{scan_id}/files` (`skip`/`limit` query params)
  - `GET /api/files/{file_id}/classification`
  - `GET /api/files/{file_id}/metadata`
  - `GET /api/files/{file_id}/thumbnail` — generates and caches a JPEG
    on first request (reusing Phase 13's `generate_thumbnail`) under
    `runtime/thumbnails/api/{file_id}.jpg`, streamed back on every
    subsequent request without regenerating.
- Unit tests for the schemas/routes via `fastapi.testclient.TestClient`
  against a temp SQLite database seeded directly (no CLI dependency
  needed at this layer) plus one integration test running the real
  `scan`→`classify`→`report` CLI pipeline and then hitting every
  endpoint against the resulting database.

### Out (later phases)

- Any POST/PUT/PATCH endpoint (`/api/scans`, destinations, move-plan,
  execute, overrides) — Phase 18 (jobs) / Phase 19 (plan/execute API).
- Server-Sent Events / progress — Phase 18.
- Any UI — Stage G.
- Vendored local Swagger UI assets — see Decisions; disabling the
  default docs is this phase's answer to "no CDN assets," not a
  deferred TODO.

## Source of truth

- README §25 "API inicial" — the "Scans"/"Classificação" route groups
  this phase covers (GET only).
- README §20.1 Passo B — "Adicionar FastAPI para expor o core," "o
  serviço deverá escutar somente 127.0.0.1."
- README §28 "Privacidade e segurança" — listen on `127.0.0.1` only, no
  external HTTP calls, no external assets, don't expose on the local
  network, reduce sensitive metadata exposure (coordinates).
- README §14.4/§28 — coordinates excluded from default output; already
  enforced in the CLI's `inventory.json` (Phase 7) and now the API.
- `specs/roadmap.md` Phase 17 entry.
- `specs/tech-stack.md` "API layer (Phase B)": FastAPI on `127.0.0.1`
  only, SSE for progress (Phase 18, not this phase), local API docs.
- `specs/mission.md` principle 1 (100% local/offline, no CDN assets, no
  external network calls, `127.0.0.1` only).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| New dependencies | `fastapi`, `uvicorn[standard]` (runtime); `httpx` (dev, for `TestClient`) | `fastapi` is already pinned in `specs/tech-stack.md`; `uvicorn` is its standard local ASGI server and isn't optional for actually running the app; `httpx` is FastAPI's own documented `TestClient` transport dependency, dev-only. |
| Interactive docs (`/docs`/`/redoc`) | Disabled (`docs_url=None`, `redoc_url=None`); `/openapi.json` stays enabled | FastAPI's default Swagger UI/ReDoc pages load their JS/CSS from a CDN — a direct violation of `specs/mission.md` principle 1's "no CDN assets," which is non-negotiable. `/openapi.json` is generated in-process with zero network activity, so it stays on for any tooling that wants the schema. Vendoring a local Swagger UI bundle is a viable future alternative but out of scope for a phase whose own done criterion doesn't mention docs. |
| Response shape | Explicit Pydantic read schemas, not the raw SQLModel table objects returned as-is | Mirrors the CLI's own established pattern (`cli/scan_report.py`'s `_media_file_to_dict`/`_media_metadata_to_dict`) of a deliberately filtered view rather than a full model dump — necessary here specifically to keep GPS coordinates out of the API, not just "a schema for its own sake." |
| DB session per request | `get_engine(get_database_path())` + `create_db_and_tables` on every request, matching the CLI's own per-invocation pattern | Consistent with how every CLI command already opens its own engine; SQLite's per-call open cost is negligible at this scale and avoids introducing app-startup state this phase doesn't otherwise need. Tests override the dependency directly rather than pointing at a real file. |
| Thumbnail caching | Generate once into `runtime/thumbnails/api/{file_id}.jpg` on first request, serve the cached file on every later request | There's no persisted thumbnail from the CLI `report` command to reuse (it writes into an arbitrary `--output` directory chosen per report run); on-demand generation keyed only by `file_id` is what makes the endpoint work without depending on a prior `report` run existing. |
| `serve` CLI command | `media-organizer serve [--port 8000]`, host hardcoded to `127.0.0.1` with no override flag at all | The non-negotiable is "listen on `127.0.0.1` only" — not exposing a `--host` flag at all removes the footgun of someone passing `0.0.0.0` by habit. |

## Constraints

- **100% local and offline** (`specs/mission.md` #1): no network calls
  anywhere in this phase's code; `/docs`/`/redoc` disabled to avoid any
  CDN fetch attempt; the API never binds beyond `127.0.0.1`.
- **Read-only**: every route in this phase only reads the database and,
  for thumbnails, writes only to a local cache directory — never to the
  scanned source tree.
- **Coordinates hidden from default output** (README §14.4/§28): applied
  at the schema layer, not left to callers to remember.
