# Plan — Phase 4: Scanner

## 1. Path normalization helpers

- `backend/app/core/paths.py`:
  - `to_nfc(path_str: str) -> str` — thin wrapper over
    `unicodedata.normalize("NFC", path_str)`.
  - `relative_nfc(path: Path, root: Path) -> str` — NFC-normalized
    POSIX-style relative path string (`as_posix()`), for stable
    cross-platform storage in `MediaFile.relative_path`.
  - Keep this module free of any `Scan`/`MediaFile` knowledge — pure path
    utilities only.

## 2. Ignore rules

- `backend/app/core/ignore_patterns.py`:
  - `IGNORED_FILE_NAMES` (exact match, case-insensitive on Windows):
    `Thumbs.db`, `desktop.ini`.
  - `IGNORED_FILE_GLOBS`: `*.tmp`, `*.partial`, `~$*`, `._*`.
  - `IGNORED_DIR_NAMES`: `.Spotlight-V100`, `.Trashes`, `.fseventsd`.
  - `is_ignored_file(name: str) -> bool` and
    `is_ignored_dir(name: str) -> bool` helpers, plus a note that `.DS_Store`
    is matched by `IGNORED_FILE_NAMES` too.

## 3. Scanner service

- `backend/app/services/scanner.py`:
  - `ScanProgress` (small dataclass or named tuple: `processed_files`,
    `total_bytes_so_far`) passed to an optional `on_progress` callback.
  - `ScannerService` (or a module-level `scan_folder` function) taking a
    session/repositories, `source_root: Path`, `recursive: bool`,
    `exclude_dirs: Sequence[Path] = ()`, `batch_size: int = 200`,
    `on_progress: Callable[[ScanProgress], None] | None = None`.
  - Validates `source_root` exists and is a directory before creating the
    `Scan` row (raise a clear exception otherwise — caller/CLI in Phase 7
    turns it into a user-facing message).
  - Creates the `Scan` row (`status="running"`, `started_at=now`) via
    `ScanRepository`.
  - Walks with `os.walk(..., followlinks=False)` (or manual `Path.iterdir`
    recursion if `recursive=False` must mean "top-level only") pruning
    `IGNORED_DIR_NAMES`, symlinked directories, and any path under
    `exclude_dirs`.
  - For each remaining entry: skip ignored file names/globs and symlinked
    files; `stat()` the rest inside a `try/except OSError` — success
    builds a `MediaFile` with `processing_status="pending"`, size, mtime,
    NFC-normalized paths; failure builds a `MediaFile` with
    `processing_status="error"`, `error_code="ACCESS_ERROR"`, and the
    exception message.
  - Buffers `MediaFile` rows and flushes in batches of `batch_size` through
    `MediaFileRepository`, invoking `on_progress` after each flush.
  - On completion, updates the `Scan` row: `status="completed"`,
    `finished_at=now`, `total_files`, `total_bytes` (sum of successfully
    stat'd sizes).
  - `total_bytes` counts only successfully read files; errored entries
    contribute to `total_files` but not `total_bytes`.

## 4. Test fixtures

- Extend `backend/tests/fixtures/` (or a `backend/tests/integration/scanner_tree/`
  helper built at test time, since a nested tree with an unreadable entry
  and an NFD-named file needs runtime construction, not static committed
  binaries):
  - A pytest fixture that builds a temp nested tree with: a couple of
    ordinary files, a `Thumbs.db`, a `._sidecar` AppleDouble file, a file
    made unreadable (Windows: DACL denial or an `unittest.mock` patch on
    `Path.stat` for that one entry, since chmod-based unreadability isn't
    reliable on NTFS — pick whichever is simpler to keep deterministic),
    and a file whose name is stored NFD-normalized while an NFC-named
    sibling reference is asserted to match it.
  - Document the tree shape in a short docstring on the fixture.

## 5. Tests

- `backend/tests/unit/test_paths.py`: NFC normalization round-trips,
  including a real NFD input.
- `backend/tests/unit/test_ignore_patterns.py`: each ignored name/glob/dir
  matches; a normal filename does not.
- `backend/tests/integration/test_scanner.py`:
  - Full scan over the nested fixture tree persists the expected
    `MediaFile` count with correct `processing_status`.
  - The unreadable entry is recorded with `processing_status="error"` and
    the scan still completes (`Scan.status="completed"`).
  - The AppleDouble `._*` file and `Thumbs.db` are absent from persisted
    rows.
  - The NFD-named fixture file's persisted `relative_path`/`absolute_path`
    equal the NFC form.
  - A symlinked file/dir (if creatable in the test environment; skip with
    a reason string on platforms where symlink creation needs elevated
    privileges) is not traversed/persisted.
  - `recursive=False` only scans the top-level directory.
  - `on_progress` is invoked at least once with a growing `processed_files`
    count.
  - `Scan.total_files` / `total_bytes` match the fixture tree's expected
    values.

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
