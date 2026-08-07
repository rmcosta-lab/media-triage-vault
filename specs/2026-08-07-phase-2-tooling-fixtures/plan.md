# Plan — Phase 2: Tooling + fixtures

## 1. Vendor ExifTool; use system FFmpeg

- Download the official ExifTool Windows standalone build (exiftool.org →
  SourceForge zip, ~11 MB) and place the executable at
  `tools/exiftool/windows-x64/exiftool.exe` (rename from the distributed
  `exiftool(-k).exe`).
- Create empty `tools/exiftool/macos-arm64/` with a `.gitkeep` (git does
  not track empty directories) so the platform key space is visible.
- Do **not** vendor FFmpeg/FFprobe — per the "FFmpeg/FFprobe vendoring"
  decision in `requirements.md`, the resolver uses the system installation
  (this dev machine already has `Gyan.FFmpeg` via `winget`). No
  `tools/ffmpeg/` directory is created in this phase.
- Record the exact vendored ExifTool version in a short `tools/README.md`
  note for future upgrades, and note there that FFmpeg/FFprobe are
  resolved from the system PATH for now, with a pointer to
  `specs/tech-stack.md` for the rationale. Keep the upstream ExifTool
  license file bundled next to the executable if the distribution
  includes one.

## 2. Resolver module

- Create `backend/app/core/__init__.py`.
- Create `backend/app/core/tools.py`:
  - `PlatformKey` — literal type or small enum for `"windows-x64"` /
    `"macos-arm64"`.
  - `detect_platform_key() -> PlatformKey` — maps `sys.platform` +
    `platform.machine()` to one of the above; raises
    `UnsupportedPlatformError` for anything else.
  - `ToolName` — literal type for `"exiftool"` / `"ffmpeg"` / `"ffprobe"`.
  - `resolve_tool(name: ToolName) -> Path`:
    - For `"exiftool"`: builds the path from `detect_platform_key()` and
      `tools/exiftool/<platform>/exiftool<suffix>`; raises
      `ToolNotAvailableError` if the platform slot is empty or the file
      does not exist.
    - For `"ffmpeg"`/`"ffprobe"`: resolves via a single `shutil.which()`
      call; raises `ToolNotAvailableError` if not found on the system.
      This is the one function in the codebase allowed to do a PATH
      lookup — every other call site goes through `resolve_tool()`/
      `run_tool()` instead of touching `shutil.which`/`subprocess`
      directly, so the interim exception stays contained to one place.
  - `run_tool(name: ToolName, args: list[str], **subprocess_kwargs) ->
    subprocess.CompletedProcess[str]` — thin wrapper that resolves the
    path and calls `subprocess.run([str(path), *args], ...)` with
    `shell=False` (the default), capturing stdout/stderr as text.
  - Locate `tools/` relative to a repo-root anchor (e.g. via
    `Path(__file__).resolve().parents[N]`), not the process's current
    working directory, so the resolver works regardless of where
    `media-organizer` is invoked from.

## 3. Fixture generation

- Add `backend/tests/fixtures/` (and `backend/tests/fixtures/__init__.py`
  only if fixtures are loaded as a package; otherwise plain files).
- Write a one-time, manually-run authoring script (e.g.
  `backend/tests/fixtures/generate_fixtures.py`, not part of the pytest
  run) that produces, using the resolver from step 2:
  - `iphone_jpeg_gps.jpg` — tiny JPEG (e.g. 32×32) written with Pillow,
    then tagged via ExifTool with `Make=Apple`, `Model=iPhone 14 Pro`,
    `GPSLatitude`/`GPSLongitude` (e.g. Tokyo coordinates, reused by Phase
    11's country-resolution tests later), `DateTimeOriginal`.
  - `iphone_heic.heic` — tiny HEIC written via Pillow + `pillow-heif`,
    tagged with `Make=Apple`, `Model=iPhone 14 Pro` via ExifTool.
  - `IMG-20260730-WA0001.jpg` — tiny JPEG named to match the WhatsApp
    filename regex (README §12), no special EXIF required.
  - `Screenshot_20260730-152000.png` — tiny PNG named to match the
    screenshot filename regex (README §13).
  - `sample_video.mp4` — generated directly with FFmpeg
    (`-f lavfi -i color=... -f lavfi -i sine -t 1`), 1 second, no audio
    needed if it complicates the build — silence or color-only is fine, a
    few KB.
  - `jpeg_no_exif.jpg` — tiny JPEG written with Pillow, then stripped with
    `exiftool -all=` (or written without EXIF injection at all if Pillow's
    default save already omits it — verify with a real ExifTool read).
- Run the script once locally, commit the resulting fixture files (all
  well under 100 KB combined).
- Do **not** wire the generation script into `pytest`/CI — fixtures are
  committed artifacts, regenerated only when deliberately updated.

## 4. Smoke test

- Create `backend/tests/unit/test_tools_resolver.py`:
  - `resolve_tool("exiftool")` / `"ffmpeg"` / `"ffprobe"` return existing,
    absolute paths under `tools/`.
  - `detect_platform_key()` returns `"windows-x64"` when run on this CI/dev
    target (skip or xfail gracefully is not needed — Windows is the only
    tested platform for the MVP).
  - Monkeypatch `sys.platform`/`platform.machine()` to simulate `darwin`
    + `arm64` and assert `resolve_tool` raises `ToolNotAvailableError`
    (proves the empty macOS slot fails loudly, not silently).
- Create `backend/tests/integration/test_tools_smoke.py`:
  - Run `exiftool -j` (via `run_tool`) against each of the six fixtures;
    assert valid JSON comes back and, where relevant, the injected tags
    round-trip (`Make == "Apple"` on the iPhone JPEG, GPS present, etc.).
  - Run `ffprobe` (via `run_tool`) against `sample_video.mp4`; assert it
    reports at least one video stream.
  - Assert (via `unittest.mock.patch` on `subprocess.run` or by
    inspecting the resolved path passed to it) that the command list's
    first element is the resolved `tools/...` path, not the bare string
    `"exiftool"`/`"ffprobe"` — this is the literal "never via bare `PATH`
    lookup" done criterion.

## 5. Verification

- `uv run pytest` — includes the new unit + integration tests, green.
- `uv run ruff check .` — clean.
- `uv run ruff format --check .` — clean.
- `uv run mypy backend` — clean.
- Manual: confirm `tools/exiftool/windows-x64/exiftool.exe` is present in
  `git status`/`git add` output as a tracked binary file, that
  `tools/exiftool/macos-arm64/` exists but is empty aside from
  `.gitkeep`, and that no `tools/ffmpeg/` directory was created.
