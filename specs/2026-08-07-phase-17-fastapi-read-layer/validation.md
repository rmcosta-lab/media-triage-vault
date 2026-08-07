# Validation — Phase 17: FastAPI read layer

### Functional

- [x] `GET /api/scans/{scan_id}` serves a completed scan's summary —
      `test_get_scan_happy_path`, manual `curl`.
- [x] `GET /api/scans/{scan_id}/files` serves the file list, with
      pagination — `test_list_scan_files_happy_path_and_pagination`.
- [x] `GET /api/files/{file_id}/classification` serves a file's
      classification — `test_get_file_classification_happy_path_excludes_coordinates`.
- [x] `GET /api/files/{file_id}/metadata` serves a file's metadata —
      `test_get_file_metadata_happy_path_excludes_coordinates`.
- [x] `GET /api/files/{file_id}/thumbnail` serves a generated, cached
      JPEG thumbnail — `test_get_file_thumbnail_generates_then_caches`,
      manual `curl` (200, `image/jpeg`, 643 bytes).
- [x] Every route 404s cleanly for a missing scan/file/classification/
      metadata — one dedicated test per route.

### Roadmap done criterion

- [x] All five endpoints serve a completed scan end to end —
      `test_api_integration.py` (real `scan`→`classify` CLI pipeline
      read back through the API) and a manual `media-organizer serve`
      run with `curl` against every endpoint.

### Tests

- [x] Unit tests cover every route's happy path and 404 case via
      `TestClient` — `test_api_routes.py`, 12 tests.
- [x] `ClassificationRead`/`MediaMetadataRead` responses never contain a
      coordinate-shaped key — asserted directly in both happy-path
      tests.
- [x] Thumbnail caching covered: first request generates, second reuses
      the cached file (same bytes, unchanged mtime).
- [x] `/docs`/`/redoc` return 404; `/openapi.json` returns 200 —
      `test_docs_disabled_openapi_enabled`, confirmed again manually.
- [x] Integration test runs the real CLI pipeline and reads it back
      through the API — `test_api_integration.py`, 3 tests.

### Safety

- [x] No network call is made anywhere in `backend/app/api/` — confirmed
      by reading every module's imports (stdlib, FastAPI/Starlette,
      SQLModel, already-audited repository/service code only).
- [x] No CDN asset is loaded — interactive docs disabled
      (`docs_url=None`, `redoc_url=None`), confirmed by test and manual
      `curl /docs` → 404.
- [x] The API never binds to anything other than `127.0.0.1` — no
      `--host` option exists on `serve`; confirmed manually via
      `netstat -ano` while the server was running (`127.0.0.1:8123
      LISTENING`, nothing on `0.0.0.0`).
- [x] `gps_latitude`/`gps_longitude`/`gps_position_raw`/
      `location_information` never appear in any API response body —
      asserted in both coordinate-exclusion tests.
- [x] `MediaFileRead` never exposes `absolute_path` — asserted in
      `test_list_scan_files_happy_path_and_pagination`.
- [x] No route writes to the scanned source tree — thumbnail generation
      only writes under the (test-overridable) thumbnail cache
      directory.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!" (added
      `fastapi.Depends` to `extend-immutable-calls`, same rationale
      already applied to `typer.Argument`/`typer.Option`).
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean — "Success: no issues found in 95
      source files".
- [x] `uv run pytest` green — 260 passed (15 new: 12 API-route unit,
      3 API-integration).
- [x] `uv run media-organizer serve --help` runs without error.

### Manual

- [x] `media-organizer serve` started against a real completed scan
      (3 fixtures); every endpoint checked with `curl`: scan summary,
      file list, thumbnail (200/`image/jpeg`/643 bytes), `/docs` → 404,
      `/openapi.json` → 200. Confirmed via `netstat` that the process
      only listened on `127.0.0.1`. Runtime database temporarily swapped
      for the manual run and restored to its prior state afterward.

### Notes (non-blocking)

- `pytest` reports one `StarletteDeprecationWarning`: "Using `httpx`
  with `starlette.testclient` is deprecated; install `httpx2` instead."
  This is an upstream Starlette/httpx transition unrelated to this
  phase's code; left as-is since it doesn't affect test correctness.
