# Plan — Phase 5: Media type detection

## 1. Model changes

- `backend/app/models/media_file.py`: add `media_kind: str | None = None` and
  `extension_mismatch: bool = False` columns to `MediaFile`.
- No migration step needed (`SQLModel.metadata.create_all`, no migrations
  framework yet — `backend/app/core/db.py`); update
  `backend/tests/unit/test_models.py` if it asserts the full column set.

## 2. Detection tables

- New `backend/app/core/media_signatures.py` (or a `_tables.py` section
  inside `media_type.py` — pick whichever keeps `media_type.py` readable):
  - `EXTENSION_CATEGORY: dict[str, Literal["image", "video"]]` built from
    README §6.1 + §6.2 (→ `"image"`) and §6.3 (→ `"video"`).
  - `EXTENSION_MIME: dict[str, str]` — one MIME string per extension in the
    same three lists.

## 3. Signature sniffer

- `backend/app/services/media_type.py`:
  - `_sniff_signature(header: bytes) -> Literal["image", "video"] | None`
    implementing the magic-byte/`ftyp`/EBML/RIFF checks listed in
    `requirements.md`.
  - `read_header(path: Path, size: int = 64) -> bytes` — opens the file in
    `"rb"`, reads at most `size` bytes, lets `OSError` propagate to the
    caller (caller decides how to record it).

## 4. Combine + detect

- `MediaTypeDetection` frozen dataclass: `media_kind`, `mime_type`,
  `extension_mismatch`, `reason`.
- `detect_media_type(path: Path, extension: str) -> MediaTypeDetection`:
  1. Look up `extension_category = EXTENSION_CATEGORY.get(extension.lower())`
     and `mime_type = EXTENSION_MIME.get(extension.lower())`.
  2. Read header via `read_header`; call `_sniff_signature`.
  3. Resolve `media_kind` = signature category if recognized, else
     `extension_category`, else `"unsupported"`.
  4. `extension_mismatch` = both categories known and unequal.
  5. Build a short `reason` string (e.g. `"signature=video, extension=image
     (.jpg)"`) for future review/debugging surfaces.

## 5. Scan-level service

- `detect_media_types_for_scan(session: Session, scan_id: int, *, on_progress: Callable[[int], None] | None = None) -> MediaTypeSummary`:
  - Pull `processing_status == "pending"` rows for the scan via
    `MediaFileRepository.list_by_scan` (filter in Python, matching the
    existing repository's simple query style — no new repository method
    needed unless it gets unwieldy).
  - For each row, call `detect_media_type(Path(row.absolute_path), row.extension)`.
  - On success: set `media_kind`, `mime_type`, `extension_mismatch` on the
    row, `repository.update(row)`.
  - On `OSError`: set `error_code="SIGNATURE_READ_ERROR"`,
    `error_message=str(error)`, leave `media_kind=None`,
    `repository.update(row)`, continue.
  - `MediaTypeSummary` dataclass: counts of `image`, `video`, `unsupported`,
    `mismatches`, `read_errors`.

## 6. Fixtures

- Add `backend/tests/fixtures/misnamed_video_as_jpg.jpg`: byte-identical copy
  of `sample_video.mp4`, saved with a `.jpg` extension. Generate it the same
  way the other fixtures were made (check
  `backend/tests/fixtures/generate_fixtures.py` for the existing pattern and
  extend it, rather than hand-copying outside that script) if it writes
  fixtures reproducibly; otherwise a plain file copy committed alongside the
  others is fine.

## 7. Tests

- `backend/tests/unit/test_media_type.py`:
  - Each fixture already in `backend/tests/fixtures/` detected with the
    correct `media_kind` and `extension_mismatch=False`
    (`iphone_jpeg_gps.jpg`, `iphone_heic.heic`, `jpeg_no_exif.jpg`,
    `Screenshot_20260730-152000.png`, `IMG-20260730-WA0001.jpg`,
    `sample_video.mp4`).
  - `misnamed_video_as_jpg.jpg` → `media_kind="video"`,
    `extension_mismatch=True`.
  - Unrecognized extension + unrecognized signature → `"unsupported"`.
  - Known extension + unreadable/truncated header (signature not
    recognized) → falls back to the extension category, `extension_mismatch=False`.
  - Signature sniffer unit-tested directly against small in-memory byte
    strings for each format family (JPEG/PNG/GIF/BMP/WEBP/TIFF/RAF/HEIC
    ftyp/MP4 ftyp/AVI RIFF/EBML), not just through fixture files.
- `backend/tests/integration/test_media_type_scan.py` (or extend
  `test_scanner.py`): run `scan_folder` over the fixtures directory (or a
  temp copy), then `detect_media_types_for_scan`, and assert the persisted
  `MediaFile` rows carry the expected `media_kind`/`extension_mismatch`
  through a real SQLite session — mirrors `test_scanner.py`'s existing
  integration shape.
- Update `backend/tests/unit/test_models.py` if it enumerates `MediaFile`
  columns.

## 8. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
