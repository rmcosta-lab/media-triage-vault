# Validation — Phase 13: Thumbnails + static reports

### Functional (README §43 first-delivery checklist)

- [x] SQLite database with the inventory — already produced by `scan`
      (Phase 3/7); unchanged by this phase.
- [x] `report.json` with normalized metadata (no coordinates) is written
      to `--output` — verified by `test_generate_report_produces_full_bundle`
      and a manual `scan`→`classify`→`report` run.
- [x] `report.csv` (summarized) is written to `--output` — same test,
      one header + one row per file via `csv.reader`.
- [x] `report.html` with classification and thumbnails is written to
      `--output`, thumbnails stored in a `thumbnails/` folder relative to
      the HTML (README §19.4) — verified in the same test and by opening
      the real generated file.
- [x] `errors.log` is written to `--output` — same test, contains
      `corrupt_video.mp4`'s `VIDEO_UNREADABLE` line.
- [x] Zero modifications to any file under the scanned source root —
      SHA-256 comparison in both integration tests, plus a `git status`/
      `git diff --stat` check on `backend/tests/fixtures/` after a manual
      run directly against the real fixtures directory (clean).

### Report content (README §19.2)

- [x] `report.html` shows: generated-at timestamp, source folder, total
      file count, total size, totals by group, totals by country,
      low-confidence files, files with errors, filters, thumbnails,
      original path, media kind, source origin, image format, device
      model, capture date, country, confidence, reasons, and a manual-
      override marker when present — all rendered by
      `report.html.jinja`, asserted present in
      `test_generate_report_produces_full_bundle` and confirmed visually
      in a manual run (523-line generated HTML, correct per-fixture
      thumbnails, two "no preview available" cards for
      `corrupt_video.mp4` and the unsupported `generate_fixtures.py`
      row).
- [x] Filters (group, confidence band, has-error, country) are present
      in the HTML and implemented without any external script or CDN
      reference (README §19.4) — inline `<style>`/`<script>` only, no
      `<link>`/external `<script src>` in the template.
- [x] No `gps_latitude`/`gps_longitude` value appears anywhere in
      `report.json`, `report.csv`, or `report.html` (README §14.4/§28) —
      `ReportRow` has no coordinate fields
      (`test_report_row_has_no_coordinate_fields`) and the integration
      test greps the raw JSON text for both key names.

### Tests (fixture coverage per media kind + failure handling)

- [x] Thumbnail generation is unit-tested against every fixture kind:
      iPhone JPEG w/ GPS, HEIC, WhatsApp-named JPEG, screenshot PNG,
      no-EXIF JPEG, MP4, misnamed-video-as-`.jpg` —
      `test_thumbnails_service.py` (11 tests).
- [x] RAW/DNG path is unit-tested against a monkeypatched `rawpy` success
      case and a real-file failure case (no genuine DNG fixture exists —
      documented gap, same precedent as Phase 9's `IPhoneRawRule`) —
      `test_generate_thumbnail_raw_success_via_embedded_preview`,
      `test_generate_thumbnail_raw_failure_on_invalid_file`.
- [x] `corrupt_video.mp4` produces no thumbnail and no exception; the
      integration test confirms the report still generates completely
      (HTML/JSON/CSV/error log all written) with that row shown as
      "no preview available" —
      `test_generate_thumbnail_for_corrupt_video_fails_without_raising`
      (unit) and `test_generate_report_produces_full_bundle` (integration).
- [x] Integration test runs the full scan → detect → extract → classify
      → report pipeline over `backend/tests/fixtures/` and asserts the
      four output files plus the `thumbnails/` folder all exist with the
      expected per-fixture contents —
      `test_generate_report_produces_full_bundle`.
- [x] Fixtures are byte-identical before/after every CLI run in this
      phase's tests — SHA-256 comparison in both
      `test_report_cli.py` tests.

### Safety

- [x] No network call is made — `thumbnails.py`/`reports.py` only call
      already-audited Phase 2/6/8-12 code plus stdlib, Pillow,
      pillow-heif, rawpy, and Jinja2 (rendering a local template file) —
      confirmed by reading both modules' imports.
- [x] No source file under a scanned root is modified, moved, or deleted
      — SHA-256 comparison (automated) plus a `git status`/`git diff`
      check on the real fixtures directory after a manual run (manual).
- [x] The video thumbnail path invokes FFmpeg only through
      `run_tool("ffmpeg", [...])` — no bare command string, no
      `shell=True` — confirmed by reading `_thumbnail_from_video`.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "67 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 67 source
      files" (required importing rawpy's enum/exception types from
      `rawpy._rawpy` directly — rawpy's own `__init__.py` only re-exports
      them under `TYPE_CHECKING`, which trips mypy strict's
      no-implicit-reexport check).
- [x] `uv run pytest` green — 185 passed (18 new: 11 thumbnail unit,
      5 report unit, 2 report CLI integration).
- [x] `uv run media-organizer report --help` runs without error —
      verified manually.

### Manual

- [x] `report.html` opened in a real browser (via `Start-Process`) after
      a full `scan` → `classify` → `report` run over the fixtures;
      thumbnails confirmed rendering correctly (spot-checked
      `thumbnails/4.jpg` and `thumbnails/7.jpg` directly — correct solid
      colors matching the source fixtures) and "no preview available"
      shown for `corrupt_video.mp4` and the unsupported
      `generate_fixtures.py` row. **User should still confirm in-browser
      that toggling each filter (group, confidence, error, country)
      visibly hides/shows the expected cards** — that interaction wasn't
      independently re-verified beyond reading the filter JS.
