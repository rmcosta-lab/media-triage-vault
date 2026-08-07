# Validation — Phase 4: Scanner

### Functional (roadmap *Done when*)

- [x] Scanning a nested fixture tree persists a `Scan` row and one
      `MediaFile` row per non-ignored entry. (`test_scan_folder_persists_expected_files_and_skips_ignored`)
- [x] An unreadable entry is recorded with `processing_status="error"`
      and does not abort the scan — the `Scan` still reaches
      `status="completed"`. (`test_scan_folder_records_access_error_without_aborting`)
- [x] An AppleDouble `._*` sidecar file is skipped and has no persisted
      `MediaFile` row. (same test tree, asserted absent from persisted rows)
- [x] An NFD-named fixture file is persisted with NFC-normalized
      `absolute_path`/`relative_path`, matching its NFC-form twin. (`test_scan_folder_persists_expected_files_and_skips_ignored` + `test_relative_nfc_normalizes_nfd_component`, `test_absolute_nfc_normalizes_nfd_component`)
- [x] `Thumbs.db`, `desktop.ini`, `*.tmp`, `*.partial`, `~$*`,
      `.Spotlight-V100`, `.Trashes`, `.fseventsd` entries are all skipped.
      (`Thumbs.db`/`.Spotlight-V100` at integration level; the full set at
      unit level via `test_ignore_patterns.py`)
- [x] Symlinked files/directories are not followed or persisted.
      (`test_scan_folder_does_not_follow_symlinks` — ran and passed, not
      skipped, on this Windows machine)
- [x] `recursive=False` scans only the top-level directory.
      (`test_scan_folder_non_recursive_only_scans_top_level`)
- [x] Every persisted `MediaFile` has non-null `size_bytes` (successful
      entries) and correct `modified_at`. (asserted in
      `test_scan_folder_persists_expected_files_and_skips_ignored`)
- [x] `Scan.total_files` and `Scan.total_bytes` match the fixture tree's
      expected totals. (asserted in both tree tests)
- [x] `on_progress` callback fires as batches flush.
      (`test_scan_folder_invokes_progress_callback`)

### Tests

- [x] `backend/tests/unit/test_paths.py` covers NFC normalization,
      including a real NFD input.
- [x] `backend/tests/unit/test_ignore_patterns.py` covers every ignored
      name/glob/directory pattern plus a non-matching control case.
- [x] `backend/tests/integration/test_scanner.py` covers the nested tree,
      the unreadable entry, the AppleDouble sidecar, the NFD/NFC pair, and
      `recursive=False` (plus `exclude_dirs`, missing source root, and
      progress callback coverage beyond the plan's minimum).

### Safety

- [x] No network call is made anywhere in the scanner code path.
      (code inspection: `backend/app/services/scanner.py` imports only
      `os`, `pathlib`, `datetime`, `sqlmodel`, and project modules; grep
      for socket/requests/urllib/http.client/aiohttp found nothing)
- [x] No file under the scanned root is modified, renamed, or deleted by
      the scanner or its tests. (verified concretely: SHA-256 of every
      file under `backend/tests/fixtures/` compared before/after running
      `scan_folder` against it — identical)
- [x] The scanner never follows a symlink outside the scanned root.
      (`test_scan_folder_does_not_follow_symlinks`)

### Technical

- [x] `uv run ruff check .` clean.
- [x] `uv run ruff format --check .` clean.
- [x] `uv run mypy backend` clean.
- [x] `uv run pytest` green. (49 passed)
