# Plan — Phase 6: Batch metadata extraction

## 1. Model

- New `backend/app/models/media_metadata.py`: `MediaMetadata` table with
  `id`, `media_file_id: int = Field(foreign_key="mediafile.id", unique=True)`,
  the normalized columns listed in `requirements.md`, and `raw_json: str | None`.
  No `from __future__ import annotations` (declares `Relationship()`); import
  `MediaFile` under `TYPE_CHECKING`.
- `backend/app/models/media_file.py`: add
  `metadata: "MediaMetadata | None" = Relationship(back_populates="media_file")`,
  importing `MediaMetadata` under `TYPE_CHECKING`.
- `backend/app/models/__init__.py`: export `MediaMetadata`.

## 2. Repository

- `backend/app/repositories/media_metadata_repository.py`: thin
  `Repository[MediaMetadata]` subclass, mirrors `MediaFileRepository`. Add a
  `get_by_media_file_id(media_file_id: int) -> MediaMetadata | None` helper
  if the service needs upsert semantics.

## 3. ExifTool field mapping

- `backend/app/services/metadata.py`:
  - `EXIFTOOL_FIELDS: tuple[str, ...]` — the exact README §8.2 list.
  - `_parse_exiftool_datetime(value: str | None) -> datetime | None` —
    parses `"YYYY:MM:DD HH:MM:SS[+-HH:MM]"`, returns `None` on any
    malformed input (never raises).
  - `_resolve_capture_datetime(tags: dict) -> datetime | None` — tries
    `DateTimeOriginal`, `CreateDate`, `MediaCreateDate`, `TrackCreateDate`
    in order.
  - `_build_media_metadata(media_file_id: int, tags: dict) -> MediaMetadata` —
    maps the remaining README §8.2 fields onto `MediaMetadata` columns,
    with `raw_json = json.dumps({k: v for k, v in tags.items() if k in EXIFTOOL_FIELDS})`.

## 4. Batch ExifTool extraction

- `_run_exiftool_batch(paths: list[Path]) -> list[dict]`: builds
  `["-j", "-n", *(f"-{field}" for field in EXIFTOOL_FIELDS), *(str(p) for p in paths)]`,
  calls `run_tool("exiftool", args, check=False)`, `json.loads(result.stdout)`.
  Returns the parsed list (same order/length as `paths`); raises a small
  `MetadataBatchError` if the array length doesn't match (defensive, should
  not happen per ExifTool's documented behavior).
- `extract_metadata_for_scan(session, scan_id, *, batch_size=200, on_progress=None) -> MetadataSummary`:
  1. Pull `processing_status == "pending"` rows with `media_kind in ("image", "video")`
     via `MediaFileRepository.list_by_scan` (filtered in Python, matching
     Phase 5's style).
  2. Chunk into `batch_size` groups; for each chunk call `_run_exiftool_batch`.
  3. For each `(row, tags)` pair: if `"Error"` in `tags`, set
     `row.error_code = "METADATA_READ_ERROR"`, `row.error_message = tags["Error"]`,
     still persist an all-`None` `MediaMetadata` row (minus `raw_json`), continue.
     Otherwise update `row.file_type`/`mime_type`/`width`/`height`/`duration_seconds`
     from the ExifTool tags when present, build and persist the `MediaMetadata`
     row via `MediaMetadataRepository.create`.
  4. For rows where `row.media_kind == "video"`, call `_validate_video(row)`
     after the metadata pass.
  5. Return `MetadataSummary` (counts: `extracted`, `video_ok`,
     `video_unreadable`, `metadata_errors`).

## 5. FFprobe video validation

- `_validate_video(row: MediaFile) -> bool`: runs
  `run_tool("ffprobe", ["-v", "error", "-print_format", "json", "-show_streams", row.absolute_path], check=False)`.
  Returns `True` if the process exits 0, stdout parses as JSON, and at
  least one entry in `streams` has `codec_type == "video"`. Otherwise sets
  `row.processing_status = "error"`, `row.error_code = "VIDEO_UNREADABLE"`,
  `row.error_message` from stderr (or a fixed message), returns `False`.

## 6. Fixture

- Extend `backend/tests/fixtures/generate_fixtures.py` with
  `make_corrupt_video()`: writes the first 256 bytes of `sample_video.mp4`
  to `corrupt_video.mp4` (still starts with a valid `ftyp` box so Phase 5
  detects it as `media_kind="video"`, but FFprobe cannot decode a stream
  from it).

## 7. Tests

- `backend/tests/unit/test_metadata.py`:
  - `_parse_exiftool_datetime` / `_resolve_capture_datetime` — valid string,
    malformed string, priority order across multiple present fields.
  - `_build_media_metadata` — full tag dict maps every column correctly;
    partial tag dict leaves the rest `None`; `raw_json` only contains
    README §8.2 keys.
  - `_run_exiftool_batch` (or the public function) invoked against real
    fixtures through the resolver — asserts one ExifTool process per batch
    by mocking `subprocess.run` call count, not per-file.
- `backend/tests/integration/test_metadata_extraction.py`:
  - scan → detect → extract over the fixtures directory through a real
    SQLite session; assert `MediaMetadata` rows exist with expected
    `make`/`model`/`gps_latitude` for `iphone_jpeg_gps.jpg`, correct
    `width`/`height`/`duration_seconds` for `sample_video.mp4`.
  - `corrupt_video.mp4` → `media_kind="video"`, `processing_status="error"`,
    `error_code="VIDEO_UNREADABLE"`.
  - one ExifTool process handles all fixtures in a single batch (mock/count
    assertion), not one per file.

## 8. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
