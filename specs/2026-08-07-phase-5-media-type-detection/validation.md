# Validation — Phase 5: Media type detection

### Functional

- [x] A misnamed fixture (video content saved with a `.jpg` extension) is
      detected as `media_kind="video"` and `extension_mismatch=True`
      (roadmap done criterion) — `test_detect_media_type_flags_misnamed_video_fixture`,
      `test_detect_media_types_for_scan_persists_results`.
- [x] Every existing correctly-named fixture (`iphone_jpeg_gps.jpg`,
      `iphone_heic.heic`, `jpeg_no_exif.jpg`, `Screenshot_20260730-152000.png`,
      `IMG-20260730-WA0001.jpg`, `sample_video.mp4`) is detected with the
      correct `media_kind` and `extension_mismatch=False` —
      `test_detect_media_type_matches_content_for_correctly_named_fixtures`
      (parametrized over all six).
- [x] `media_kind` combines extension, MIME, and file signature per README
      §6.4; an unrecognized extension and unrecognized signature together
      resolve to `media_kind="unsupported"` —
      `test_detect_media_type_unknown_extension_and_signature_is_unsupported`.
- [x] Detection runs over an existing scan's `MediaFile` rows
      (`processing_status == "pending"`) and persists results through
      `MediaFileRepository`, without re-walking the filesystem —
      `detect_media_types_for_scan` reads via `MediaFileRepository.list_by_scan`
      only, verified by `test_detect_media_types_for_scan_persists_results`.

### Tests

- [x] Unit tests cover the signature sniffer for every format family listed
      in `requirements.md` (JPEG, PNG, GIF, BMP, WEBP, TIFF-based RAW, RAF,
      HEIC `ftyp`, MP4/MOV `ftyp`, AVI `RIFF`, MKV/WEBM `EBML`) —
      `test_sniff_signature`, 13 cases.
- [x] Unit tests cover `detect_media_type` combining logic: signature wins
      when recognized, extension fallback when signature is unrecognized,
      mismatch flagged only when both categories are known and disagree —
      `test_detect_media_type_falls_back_to_extension_when_signature_unrecognized`,
      `test_detect_media_type_flags_misnamed_video_fixture`.
- [x] Integration test runs scan → detect over fixtures through a real
      SQLite session and asserts persisted columns —
      `test_detect_media_types_for_scan_persists_results`.
- [x] A read error during detection (e.g. file removed after scan, before
      detection) is recorded (`error_code="SIGNATURE_READ_ERROR"`) without
      aborting the batch —
      `test_detect_media_types_for_scan_records_read_errors_without_aborting`.

### Safety

- [x] No network call is made — `media_signatures.py`/`media_type.py` use
      only `pathlib`/stdlib file I/O; no socket/HTTP imports anywhere in the
      new code.
- [x] No source file under a scanned root is modified, moved, or deleted —
      detection only opens files `"rb"` and reads a bounded header;
      `git status` after the full test run shows only new files plus the
      two files intentionally edited (`media_file.py`, `generate_fixtures.py`) —
      every pre-existing fixture is untouched.
- [x] No external tool (ExifTool/FFprobe) is invoked this phase — pure
      Python signature checks only; `media_type.py` has no
      `backend.app.core.tools` import.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "32 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 32 source files".
- [x] `uv run pytest` green — 73 passed (24 new: 13 signature-sniffer cases,
      6 correctly-named-fixture cases, 5 more unit/integration cases).
