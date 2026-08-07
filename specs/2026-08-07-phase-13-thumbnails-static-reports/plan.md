# Plan — Phase 13: Thumbnails + static reports

## 1. Dependencies

- `pyproject.toml`: add `rawpy>=0.24.0` and `jinja2>=3.1.0` to
  `[project].dependencies`.
- `[[tool.mypy.overrides]]`: add `module = "rawpy"`,
  `ignore_missing_imports = true` (Jinja2 ships its own types, no override
  needed).
- `uv sync` to lock.

## 2. Thumbnail service

- New `backend/app/services/thumbnails.py`:
  - `THUMBNAIL_MAX_DIMENSION = 320`, `THUMBNAIL_QUALITY = 82`.
  - `RAW_EXTENSIONS` — import the frozenset already defined in
    `services/classification.py` rather than redefining it.
  - `ThumbnailResult` frozen dataclass: `success: bool`,
    `error_code: str | None`, `error_message: str | None`.
  - `generate_thumbnail(media_file: MediaFile, destination: Path) ->
    ThumbnailResult`: dispatch on `media_file.media_kind` /
    `media_file.extension.lower()`:
    - `media_kind == "video"` → `_thumbnail_from_video`.
    - extension in `RAW_EXTENSIONS` → `_thumbnail_from_raw`.
    - extension in `{".heic", ".heif"}` → `_thumbnail_from_heif`.
    - `media_kind == "image"` (everything else) → `_thumbnail_from_image`.
    - anything else → `ThumbnailResult(False, "UNSUPPORTED_MEDIA_KIND", ...)`.
  - `_thumbnail_from_image`: `Image.open(path)`, convert P/RGBA to RGB
    against a white background, `.thumbnail((MAX, MAX))`, save as JPEG to
    `destination`. Catches `PIL.UnidentifiedImageError`/`OSError`.
  - `_thumbnail_from_heif`: `pillow_heif.register_heif_opener()` once at
    module import, then same body as `_thumbnail_from_image`.
  - `_thumbnail_from_raw`: `rawpy.imread(str(path))` in a `with` block;
    try `.extract_thumb()` first (`rawpy.ThumbFormat.JPEG` → write bytes
    directly; `rawpy.ThumbFormat.BITMAP` → wrap in `Image.fromarray` and
    save); on `rawpy.LibRawNoThumbnailError`/`rawpy.LibRawFileUnsupportedError`
    fall back to `.postprocess()` → `Image.fromarray(...)` →
    `.thumbnail()` → save. Catches `rawpy.LibRawError`/`OSError`.
  - `_thumbnail_from_video`: build the FFmpeg args (`-ss 00:00:01 -i
    <path> -frames:v 1 -vf scale='min(320,iw)':-2 -y <destination>`),
    call `run_tool("ffmpeg", args, timeout=30)`. Non-zero return code
    (e.g. a corrupt/near-empty video with no seekable frame at 1s) is
    caught and reported as a `ThumbnailResult` failure, not raised —
    matches the `corrupt_video.mp4` fixture case.
  - `ThumbnailSummary` frozen dataclass: `generated`, `failed`, `skipped`
    counts.
  - `generate_thumbnails_for_scan(session, scan_id, thumbnails_dir: Path,
    *, on_progress=None) -> dict[int, ThumbnailResult]`: iterate
    `MediaFileRepository.list_by_scan(scan_id)` filtered to
    `media_kind in ("image", "video")` and `error_code is None`
    (skip files that never extracted, e.g. `VIDEO_UNREADABLE`, but still
    report them as "skipped" rather than silently dropped), write to
    `thumbnails_dir / f"{media_file.id}.jpg"`, return a
    `{media_file_id: ThumbnailResult}` map for `reports.py` to consume.

## 3. Report service

- New `backend/app/services/reports.py`:
  - `ReportRow` frozen dataclass mirroring the `report.json`/`.csv` per-file
    shape from `requirements.md` (relative_path, media_kind, extension,
    size_bytes, width/height/duration, capture fields from
    `MediaMetadata`, `effective_routing_group`, `confidence`,
    `requires_review`, `reasons`, `country_code`, `country_name`,
    `manual_override: bool`, `error_code`/`error_message`,
    `thumbnail_path: str | None`).
  - `ReportSummary` frozen dataclass: `total_files`, `total_bytes`,
    `thumbnails_generated`, `thumbnails_failed`, `low_confidence_count`,
    `error_count`, `totals_by_group: dict[str, int]`,
    `totals_by_country: dict[str, int]`.
  - `_build_rows(session, scan_id, thumbnail_results) -> list[ReportRow]`:
    join `MediaFileRepository.list_by_scan` with
    `MediaMetadataRepository.get_by_media_file_id` and
    `ClassificationRepository.get_by_media_file_id` per row; reuse
    `_media_metadata_to_dict`'s field subset (import from
    `cli/scan_report.py`) so coordinates never leak in.
  - `generate_report(session, scan_id, output_dir: Path, *,
    on_progress=None) -> ReportSummary`:
    1. load `Scan` (source_root, timestamps) via `ScanRepository`.
    2. `(output_dir / "thumbnails").mkdir(parents=True, exist_ok=True)`.
    3. `thumbnail_results = generate_thumbnails_for_scan(...)`.
    4. `rows = _build_rows(...)`; compute totals.
    5. write `report.json` (`json.dumps(..., default=_json_default,
       indent=2, ensure_ascii=False)`, reusing `_json_default` from
       `cli/scan_report.py`).
    6. write `report.csv` via `csv.DictWriter` over the same rows
       (reasons joined with `"; "`).
    7. render `report.html.jinja` via a `jinja2.Environment(loader=
       FileSystemLoader(TEMPLATES_DIR), autoescape=True)` and write
       `report.html`.
    8. `write_error_log(output_dir / "errors.log", media_file_rows)`
       (Phase 7 helper, imported from `cli/scan_report.py`).
    9. return `ReportSummary`.

## 4. Template

- New `backend/app/templates/report.html.jinja`:
  - Header: generated-at timestamp, source root, total files, total
    size, totals-by-group and totals-by-country tables (README §19.2).
  - Inline `<style>` (no external stylesheet) — simple grid of file
    cards.
  - Inline `<script>` — filter controls (group `<select>`, "low
    confidence only" checkbox, "errors only" checkbox, country
    `<select>`) toggling row visibility via `data-group`,
    `data-requires-review`, `data-has-error`, `data-country` attributes;
    no fetch/XHR, no external script tag.
  - Per-file card: thumbnail `<img>` (relative `thumbnails/<id>.jpg` src,
    or a "no preview" placeholder block when `thumbnail_path` is `null`),
    original relative path, media kind, source origin, image format,
    device make/model, capture date, country name, confidence,
    requires-review flag, reasons list, manual-override marker.

## 5. CLI wiring

- `backend/app/cli/main.py`:
  - `@app.command("report")` — `report_command(scan_id: int =
    typer.Option(..., "--scan-id"), output: Path = typer.Option(...,
    "--output"), database: Path | None = typer.Option(None,
    "--database", hidden=True))`: creates `output`, opens the session,
    calls `generate_report` with an `on_progress` that echoes thumbnail
    progress, then prints a summary line (totals by group, thumbnails
    generated/failed, low-confidence count, error count) and the three
    output paths (`report.html`/`.json`/`.csv`) plus `errors.log`.

## 6. Tests

- `backend/tests/unit/test_thumbnails_service.py`:
  - One case per fixture kind: `iphone_jpeg_gps.jpg`, `iphone_heic.heic`,
    `IMG-20260730-WA0001.jpg`, `Screenshot_20260730-152000.png`,
    `jpeg_no_exif.jpg` → `_thumbnail_from_image`/`_thumbnail_from_heif`
    succeed, file exists, within the 320px cap.
  - `sample_video.mp4` → `_thumbnail_from_video` succeeds.
  - `corrupt_video.mp4` → `_thumbnail_from_video` returns
    `ThumbnailResult(success=False)`, no destination file left behind,
    no exception raised.
  - `misnamed_video_as_jpg.jpg` → dispatch follows `media_kind` (already
    `"video"` per Phase 5), not the `.jpg` extension — succeeds via the
    video path.
  - RAW/DNG: one test monkeypatching `rawpy.imread` to return a fake
    reader whose `extract_thumb()` yields a tiny in-memory JPEG (success
    path, writes the thumbnail); one test pointing `_thumbnail_from_raw`
    at a file containing arbitrary non-raw bytes named `sample.dng`
    (failure path — `rawpy.LibRawError`/`OSError` caught, returns
    `ThumbnailResult(success=False)`).
  - `UNSUPPORTED_MEDIA_KIND` case for a `media_kind="unsupported"` file.
- `backend/tests/unit/test_reports_service.py`:
  - `_build_rows` produces one `ReportRow` per classified file with the
    expected field values from synthetic `MediaFile`/`MediaMetadata`/
    `Classification` rows; asserts no `gps_latitude`/`gps_longitude`
    attribute/key ever appears on the row or in its `__dict__`.
  - Totals-by-group/country computation over a small synthetic set.
- `backend/tests/integration/test_report_cli.py`:
  - Full pipeline over the fixtures directory (temp copy + temp
    database, same pattern as `test_classify_cli.py`): `scan` → detect →
    extract → `classify_scan` → `generate_report`. Assert:
    `report.json`/`report.csv`/`report.html`/`errors.log` all exist in
    `--output`; `thumbnails/` contains a `.jpg` per successfully
    thumbnailed file and none for `corrupt_video.mp4`;
    `report.html` contains each fixture's relative path, a
    `confidence=`-style figure, and the filter controls (`<select>`
    presence); `report.json` has no `gps_latitude`/`gps_longitude` key
    anywhere in its text; `report.csv` has one data row per file plus a
    header.
  - CLI `report --scan-id --output` (via `CliRunner`) exits `0` and its
    stdout names all four output files.
  - No fixture file under `backend/tests/fixtures/` is modified (SHA-256
    comparison), matching every prior CLI integration test.

## 7. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer report --help` runs cleanly.
- Manual: run `scan` → `classify` → `report` against
  `backend/tests/fixtures/`, open the resulting `report.html` in a real
  browser, confirm thumbnails render and the group/confidence/error/
  country filters actually hide/show rows.
