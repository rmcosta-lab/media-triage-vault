# Validation — Phase 2: Tooling + fixtures

### Functional

- [x] `tools/exiftool/windows-x64/` contains a working ExifTool executable.
      (`exiftool.exe -ver` → `13.59`; `tools/exiftool/windows-x64/`
      contains `exiftool.exe` + sibling `exiftool_files/` runtime, ~35 MB.)
- [x] `tools/exiftool/macos-arm64/` exists but holds no binary; no
      `tools/ffmpeg/` directory is created this phase. (`.gitkeep` only
      under `macos-arm64/`; `git add -n tools/` shows no `ffmpeg` paths —
      confirmed the FFmpeg/FFprobe vendoring decision was followed.)
- [x] `backend/app/core/tools.py` exposes a resolver: ExifTool resolution
      is keyed on `sys.platform` + `platform.machine()` against the
      vendored path; FFmpeg/FFprobe resolution is a single, centralized
      `shutil.which()` lookup inside `resolve_tool()`. (`detect_platform_key()`
      → `"windows-x64"`; `resolve_tool("exiftool")` returns the vendored
      path; `resolve_tool("ffmpeg")`/`resolve_tool("ffprobe")` return the
      `winget`-installed paths — verified interactively and via
      `test_tools_resolver.py`.)
- [x] The resolver raises a clear, typed error (not a silent fallback) when
      asked to resolve ExifTool on a platform with an empty vendor slot,
      or FFmpeg/FFprobe when not present on the system.
      (`test_resolve_vendored_tool_raises_on_empty_platform_slot` and
      `test_resolve_system_tool_raises_when_missing_from_path` — both
      pass, raising `ToolNotAvailableError`.)
- [x] All six named fixtures exist under `backend/tests/fixtures/`: iPhone
      JPEG with GPS, HEIC, WhatsApp-named file, screenshot-named PNG,
      small MP4, JPEG without EXIF — each small. (Largest fixture is
      `sample_video.mp4` at 1.9 KB; all six total under 8 KB.)
- [x] A smoke test runs real ExifTool (`-j`) and FFprobe against the
      fixtures through `resolve_tool()`/`run_tool()`. For ExifTool, the
      test asserts the invoked path is the vendored `tools/...` path, not
      a bare `"exiftool"` string. **Known deviation from the roadmap's
      literal wording** ("never via bare PATH lookup"): FFprobe is
      resolved via `shutil.which` for this phase (see requirements.md) —
      the test instead asserts this resolution happens exactly once,
      inside `resolve_tool()`, and that no other call site references a
      bare `"ffmpeg"`/`"ffprobe"` string. (`test_exiftool_is_invoked_via_resolved_path_not_bare_command`
      and `test_ffprobe_is_invoked_via_resolver_lookup_not_a_bare_string`
      — both pass. This deviation was discussed with and approved by the
      user during implementation; recorded in `specs/tech-stack.md` and
      `AGENTS.md`.)

### Tests

- [x] Unit test covers `resolve_tool` success for `exiftool`, `ffmpeg`,
      `ffprobe` on the current (Windows) platform.
      (`test_resolve_exiftool_returns_vendored_path`,
      `test_resolve_ffmpeg_and_ffprobe_return_existing_paths` — pass.)
- [x] Unit test covers the empty-slot failure path (simulated macOS
      platform) raising the typed error, plus the analogous
      missing-from-PATH failure for the system-resolved tools.
      (`test_resolve_vendored_tool_raises_on_empty_platform_slot`,
      `test_resolve_system_tool_raises_when_missing_from_path`,
      `test_detect_platform_key_raises_for_unsupported_combination` —
      pass.)
- [x] Integration test covers ExifTool JSON extraction against each
      fixture, asserting injected tags round-trip where applicable
      (`Make`, GPS coordinates). (5 parametrized reads +
      `test_exiftool_reports_injected_gps_and_make`,
      `test_exiftool_reports_apple_make_on_heic_fixture`,
      `test_exiftool_reports_no_exif_for_stripped_fixture` — all pass.)
- [x] Integration test covers FFprobe reporting a video stream for the
      sample MP4. (`test_ffprobe_reports_video_stream_for_sample_video` —
      pass.)
- [x] `uv run pytest` green, including the new unit and integration
      tests. (18 passed in 2.54s — 6 unit + 11 integration in this phase's
      new files, plus the Phase 1 bootstrap test.)

### Safety

- [x] No network call is made by the resolver, `run_tool`, or any test —
      only local subprocess invocations of the vendored/system binaries.
      (Grepped `backend/` for `requests.`, `urllib.request`, `httpx.`,
      `socket.`, `http.client` — no matches. Binary downloads for vendoring
      were a one-time manual dev-machine step, same pattern as `uv sync`
      in Phase 1 — not part of the shipped app or test suite.)
- [x] No source file outside `tools/` and `backend/tests/fixtures/` is
      created or modified by this phase; no user file anywhere is
      touched. (`git status --porcelain` shows only new files under
      `tools/`, `backend/app/core/`, `backend/tests/`,
      `specs/2026-08-07-phase-2-tooling-fixtures/`, plus modifications to
      `AGENTS.md`, `pyproject.toml`, `specs/tech-stack.md`, and `uv.lock`
      — all expected. Fixtures are synthetic files this phase created,
      not real user media.)
- [x] Every ExifTool/FFprobe/FFmpeg invocation goes through
      `resolve_tool()`/`run_tool()` and uses a `subprocess` argument list
      (`shell=False`) — grep confirms no bare `"exiftool"`/`"ffmpeg"`/
      `"ffprobe"` string is passed to `subprocess` anywhere outside
      `backend/app/core/tools.py` itself. (Grepped for
      `subprocess.(run|Popen|call|check_call|check_output)` across
      `backend/` — the only call site is `tools.py:88`; test files only
      reference `subprocess.run` to wrap/patch it for assertions.)

### Technical

- [x] `uv run ruff check .` clean. (`All checks passed!`)
- [x] `uv run ruff format --check .` clean. (`11 files already
      formatted`.)
- [x] `uv run mypy backend` clean. (`Success: no issues found in 11
      source files` — required adding a `pillow_heif` override
      (`ignore_missing_imports`, no type stubs published) and switching
      the resolver-monkeypatch tests to string-path `monkeypatch.setattr`
      calls instead of direct module-attribute access, since mypy strict
      mode flags `sys`/`platform`/`shutil` as non-reexported attributes
      of `backend.app.core.tools`.)
- [x] `uv run pytest` green. (18 passed.)
