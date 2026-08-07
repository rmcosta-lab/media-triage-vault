# Plan — Phase 17: FastAPI read layer

## 1. Dependencies

- `uv add fastapi uvicorn[standard]`; `uv add --group dev httpx`.
- `specs/tech-stack.md`: add `Uvicorn` and note `httpx` (test-only) under
  "API layer (Phase B)".

## 2. Schemas

- New `backend/app/api/schemas.py`, Pydantic `BaseModel` subclasses with
  `model_config = ConfigDict(from_attributes=True)`:
  - `ScanRead`: `id`, `source_root`, `recursive`, `status`,
    `total_files`, `processed_files`, `total_bytes`, `created_at`,
    `started_at`, `finished_at` — full passthrough (`Scan` has no
    sensitive fields).
  - `MediaFileRead`: `id`, `scan_id`, `relative_path`, `file_name`,
    `extension`, `mime_type`, `file_type`, `media_kind`, `size_bytes`,
    `width`, `height`, `duration_seconds`, `extension_mismatch`,
    `modified_at`, `processing_status`, `error_code`, `error_message`
    (no `absolute_path` — the API never needs to leak a full local
    filesystem path to a browser client).
  - `ClassificationRead`: `id`, `media_file_id`, `media_kind`,
    `source_origin`, `image_format`, `automatic_routing_group`,
    `manual_routing_group`, `effective_routing_group`, `confidence`,
    `requires_review`, `reasons_json`, `device_make`, `device_model`,
    `captured_at`, `country_code`, `country_name`, `override_timestamp`
    — `gps_latitude`/`gps_longitude` omitted.
  - `MediaMetadataRead`: `id`, `media_file_id`, `capture_datetime`,
    `make`, `model`, `software`, `lens_model`, `camera_serial_number`,
    `handler_description`, `compressor_name`, `encoder`, `rotation`,
    `profile_description`, `color_space` — `gps_latitude`/
    `gps_longitude`/`gps_position_raw`/`location_information` omitted
    (matches `cli/scan_report.py::_media_metadata_to_dict` exactly).

## 3. Session dependency

- New `backend/app/api/deps.py`:
  - `get_session_dependency() -> Iterator[Session]`: `engine =
    get_engine(get_database_path())`; `create_db_and_tables(engine)`;
    `with Session(engine) as session: yield session`.

## 4. Routes

- New `backend/app/api/routes.py`, `router = APIRouter()`:
  - `GET /scans/{scan_id}` → `ScanRead`; 404 if missing.
  - `GET /scans/{scan_id}/files?skip=0&limit=200` → `list[MediaFileRead]`;
    404 if the scan itself doesn't exist; empty list if the scan exists
    but has no files (not an error).
  - `GET /files/{file_id}/classification` → `ClassificationRead`; 404 if
    the file doesn't exist or has no classification yet.
  - `GET /files/{file_id}/metadata` → `MediaMetadataRead`; 404 if the
    file doesn't exist or has no metadata yet.
  - `GET /files/{file_id}/thumbnail` → `FileResponse` (`image/jpeg`);
    404 if the file doesn't exist; on first request, generate into
    `<repo_root>/runtime/thumbnails/api/{file_id}.jpg` via
    `services.thumbnails.generate_thumbnail`, returning 422 with the
    thumbnail error code/message if generation fails; reuse the cached
    file on every later request without regenerating.

## 5. App + CLI wiring

- New `backend/app/api/app.py`: `create_app() -> FastAPI` —
  `FastAPI(title="Local Media Organizer API", docs_url=None,
  redoc_url=None)`, `app.include_router(router, prefix="/api")`; module-
  level `app = create_app()` for `uvicorn` to import.
- `backend/app/cli/main.py`: `@app.command("serve")` —
  `serve_command(port: int = typer.Option(8000, "--port"))`: prints the
  bound URL, then `uvicorn.run("backend.app.api.app:app", host="127.0.0.1",
  port=port)`. No `--host` option.

## 6. Tests

- `backend/tests/unit/test_api_routes.py`: `TestClient` against
  `create_app()` with `app.dependency_overrides[get_session_dependency]`
  pointed at a temp SQLite engine seeded directly (scan + media file +
  classification + metadata rows built the same way the service-layer
  unit tests already do). Cover:
  - `GET /api/scans/{id}` happy path and 404.
  - `GET /api/scans/{id}/files` happy path (including `skip`/`limit`)
    and 404 for a missing scan.
  - `GET /api/files/{id}/classification` happy path, 404 for a missing
    file, 404 for a file with no classification yet; response body
    never contains `gps_latitude`/`gps_longitude` keys.
  - `GET /api/files/{id}/metadata` happy path, 404 for a missing file,
    404 for a file with no metadata yet; response body never contains
    any of the four coordinate-shaped keys.
  - `GET /api/files/{id}/thumbnail`: 404 for a missing file; a real
    image fixture returns `200`/`image/jpeg` and the cache file appears
    under a temp `runtime/thumbnails/api/`; a second request returns the
    same bytes without the mtime changing (proves it's served from
    cache, not regenerated).
  - `/docs`, `/redoc` return `404`; `/openapi.json` returns `200`.
- `backend/tests/integration/test_api_integration.py`: run `scan` →
  `classify` CLI commands against `backend/tests/fixtures/` into a temp
  database, point the API at that same database file (override the
  dependency to open it directly, no CLI/dependency_overrides trickery
  needed since it's a real file), then hit every endpoint and assert
  the data matches what the CLI produced (e.g. `GET .../files` count
  equals the fixture count, a WhatsApp fixture's classification group
  matches).

## 7. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer serve --help` runs cleanly.
- Manual: run the full `scan`→`classify`→`report` pipeline against
  fixtures, start `media-organizer serve`, and `curl` each endpoint
  (including a thumbnail) against the resulting scan.
