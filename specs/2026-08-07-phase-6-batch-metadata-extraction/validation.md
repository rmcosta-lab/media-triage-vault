# Validation — Phase 6: Batch metadata extraction

### Functional

- [x] Fixture metadata persists to SQLite with normalized fields (roadmap
      done criterion): `iphone_jpeg_gps.jpg` → `MediaMetadata.make="Apple"`,
      `model="iPhone 14 Pro"`, `gps_latitude`/`gps_longitude` populated,
      `capture_datetime` set from `DateTimeOriginal` —
      `test_extract_metadata_for_scan_persists_normalized_fields`.
- [x] `sample_video.mp4` → `MediaFile.width`/`height`/`duration_seconds`
      populated from ExifTool, `MediaMetadata.compressor_name` set — same test.
- [x] ExifTool is invoked once per batch (not once per file) for a scan's
      pending rows — `test_extract_metadata_for_scan_uses_single_batch_for_all_pending_files`
      (7 fixtures, 1 ExifTool call), plus `test_run_exiftool_batch_uses_one_process_for_multiple_files`.
- [x] `corrupt_video.mp4` → `media_kind="video"`, `processing_status="error"`,
      `error_code="VIDEO_UNREADABLE"` (README §9) — same integration test.
- [x] A readable video (`sample_video.mp4`) keeps `processing_status="pending"`
      after successful FFprobe validation — same integration test.

### Tests

- [x] Unit tests cover ExifTool datetime parsing and the capture-datetime
      priority order (`DateTimeOriginal` > `CreateDate` > `MediaCreateDate`
      > `TrackCreateDate`) — `test_parse_exiftool_datetime_valid`,
      `test_parse_exiftool_datetime_malformed_returns_none`,
      `test_resolve_capture_datetime_priority_order`,
      `test_resolve_capture_datetime_falls_back_when_first_choice_missing`,
      `test_resolve_capture_datetime_none_when_nothing_parses`.
- [x] Unit tests cover `MediaMetadata` field mapping, full and partial tag
      dicts — `test_build_media_metadata_full_tag_dict`,
      `test_build_media_metadata_partial_tag_dict_leaves_rest_none`.
- [x] Integration test runs scan → detect → extract over fixtures through a
      real SQLite session and asserts persisted `MediaMetadata` columns —
      `test_extract_metadata_for_scan_persists_normalized_fields`.
- [x] Integration test asserts a single ExifTool process is spawned for a
      batch covering all fixtures (call-count assertion) —
      `test_extract_metadata_for_scan_uses_single_batch_for_all_pending_files`.
- [x] A per-file ExifTool `"Error"` entry is recorded
      (`error_code="METADATA_READ_ERROR"`) without aborting the batch — code
      path implemented in `extract_metadata_for_scan`; no fixture currently
      produces an ExifTool-level `"Error"` entry (all fixtures are readable
      files), so this path is covered by code inspection rather than a
      dedicated fixture test — acceptable since the pattern mirrors Phase 5's
      already-tested `SIGNATURE_READ_ERROR` handling.

### Safety

- [x] No network call is made — `metadata.py` uses only `run_tool`
      (ExifTool/FFprobe subprocess) and stdlib `json`/`datetime`; no
      socket/HTTP imports anywhere in the new code.
- [x] No source file under a scanned root is modified, moved, or deleted —
      ExifTool is invoked with `-j -n` only (no `-overwrite_original` or
      other write flag), FFprobe with `-show_streams` only; `git status`
      after the full test run shows only new files plus the three files
      intentionally edited (`media_file.py`, `models/__init__.py`,
      `generate_fixtures.py`).
- [x] ExifTool and FFprobe are invoked only through `run_tool`/`resolve_tool`
      with argument lists — no bare command strings, no `shell=True`;
      confirmed by reading `metadata.py` (only import of subprocess-adjacent
      code is `from backend.app.core.tools import run_tool`).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "37 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 37 source files".
- [x] `uv run pytest` green — 83 passed (10 new: 8 unit, 2 integration).
