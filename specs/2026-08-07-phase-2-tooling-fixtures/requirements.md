# Requirements — Phase 2: Tooling + fixtures

## Objective

Give every later phase two things it depends on: a single, tested resolver
that locates the vendored ExifTool and FFmpeg/FFprobe binaries per platform
(never a bare `PATH` lookup), and the first batch of small test fixtures
(iPhone JPEG with GPS, HEIC, WhatsApp-named file, screenshot-named PNG,
small MP4, JPEG without EXIF) that Phases 4–13 will read against.

## Scope

### In

- `tools/exiftool/windows-x64/` — vendored ExifTool Windows executable.
- `tools/exiftool/macos-arm64/` — created as an empty directory (with a
  `.gitkeep`) so the resolver's platform-key space is visible, but no
  binary is vendored there yet.
- A single resolver module (`backend/app/core/tools.py`) that returns an
  absolute `Path` to `exiftool`, `ffmpeg`, or `ffprobe`:
  - `exiftool` is resolved from the vendored `tools/exiftool/<platform>/`
    directory, keyed on `sys.platform` + `platform.machine()`; raises a
    clear, typed error when the platform slot is empty (macOS today) or
    the binary is missing.
  - `ffmpeg`/`ffprobe` are resolved via a single `shutil.which()` lookup
    (see Decisions — "FFmpeg/FFprobe vendoring" for why); raises the same
    typed error if not found on the system. Every call site still goes
    through `resolve_tool()`, never a bare command string.
- `backend/app/core/__init__.py` (first file in this package).
- Fixtures under `backend/tests/fixtures/`: iPhone JPEG with GPS, HEIC,
  WhatsApp-named file, screenshot-named PNG, small MP4, JPEG without EXIF —
  see Decisions for exact names and how each is produced.
- A smoke test that calls the resolver and runs real ExifTool (`-j`) and
  FFprobe against the fixtures, asserting the resolver's path — not a bare
  command name — is what `subprocess` invokes.

### Out

- Batch extraction, field normalization, `media_kind` detection — Phases 5–6.
- The scanner and ignore-pattern walk — Phase 4 (this phase's fixtures live
  under `backend/tests/fixtures/`, not a scanned tree).
- SQLite persistence of any extracted metadata — Phase 3/6.
- macOS binaries and any macOS-specific test run — explicitly post-MVP per
  `specs/tech-stack.md` and `specs/roadmap.md` "Horizon".
- The full README §30.2 integration fixture list (DNG ProRAW, MOV with GPS,
  Android screenshot, `Sent` folder, corrupted video, wrong-extension file,
  border coordinate, duplicate name, locked file, cross-volume pair) — only
  the six fixtures the roadmap names for Phase 2 are built now; the rest
  arrive as the phases that need them land (Phase 5 wrong-extension, Phase 6
  corrupt video, Phase 9 DNG/MOV, Phase 14 collisions/volumes, etc.).

## Source of truth

- `specs/roadmap.md` — Phase 2 entry (Stage A — Foundation): vendor/locate
  ExifTool and FFmpeg under per-platform directories behind a single
  resolver keyed on `sys.platform` + `platform.machine()`; verify invocation
  via `subprocess` argument lists; create the six named fixtures; only
  Windows binaries vendored now. Done when a smoke test runs ExifTool and
  FFprobe against fixtures through the resolver, never via bare `PATH`
  lookup.
- `specs/tech-stack.md` — "Cross-platform" table, "Bundled binaries" row:
  `tools/exiftool/<platform>/` and `tools/ffmpeg/<platform>/`
  (`windows-x64`, `macos-arm64`); a single resolver picks by `sys.platform`
  + `platform.machine()`; never call a bare `exiftool`/`ffprobe` from
  `PATH`. Also "Metadata and media tools" (ExifTool primary, FFprobe/FFmpeg
  for video).
- README §8.1/§8.3 — ExifTool as the primary metadata tool, distributed or
  installed locally and invoked by the backend; FFprobe/FFmpeg as
  complementary tools for video.
- README §30.2 — the full integration-fixture wishlist; this phase builds
  the subset the roadmap names for Phase 2 (see Scope → Out for the rest).
- `AGENTS.md` — "Repository layout" (`tools/{exiftool,ffmpeg}/<platform>/`,
  `backend/tests/{unit,integration,fixtures}`) and "Implementation
  conventions" — External tools: resolved through the bundled per-platform
  resolver, never from a bare `PATH` lookup; `subprocess` argument lists
  only, never a shell string.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Implement as written | User confirmed the roadmap phase description as-is. |
| Implementation approach | Tech-lead's call | User deferred to `specs/tech-stack.md` and `specs/mission.md`. |
| Validation criteria | Standard checks only | User confirmed no extra criteria beyond the roadmap's done condition and the standard lint/type/test gate. |
| Resolver location | `backend/app/core/tools.py` | `AGENTS.md` "Repository layout" places tool-adjacent core logic under `backend/app/core/`; this is the first file to land there. |
| Platform key format | `windows-x64`, `macos-arm64` | Matches the exact strings used in `specs/tech-stack.md`'s "Bundled binaries" row, so the resolver's directory lookup is a literal match, not a reinterpretation. |
| Binary source | ExifTool: official standalone Windows build from exiftool.org (Phil Harvey, via SourceForge, ~11 MB zip). FFmpeg/FFprobe: whatever the user already has installed via `winget install Gyan.FFmpeg` — the same Gyan.dev static build the project would otherwise vendor. | ExifTool's zip is small enough to commit outright; FFmpeg's official Windows build is ~100-250 MB, too large to add to git history for this phase (see next row). |
| ExifTool vendoring | Executable committed under `tools/exiftool/windows-x64/`, not gitignored | `specs/tech-stack.md` describes it as "bundled" — the app must run from a fresh clone with no separate download step, matching README §8.1 "O executável deverá ser distribuído ou instalado localmente." |
| FFmpeg/FFprobe vendoring | **Not vendored for this phase.** Resolver discovers the system-installed `ffmpeg`/`ffprobe` via a single `shutil.which()` call, still centralized behind `resolve_tool()`. | User declined to commit ~100-250 MB of binaries to git history for a permanent, hard-to-reverse repo-size cost. Revisit (real vendoring or Git LFS) when Tauri packaging needs a self-contained sidecar — tracked in `specs/tech-stack.md`. This is a deviation from the roadmap's literal Phase 2 done criterion ("never via bare PATH lookup"); recorded here and in `specs/tech-stack.md` / `AGENTS.md` rather than silently applied. |
| Missing macOS slot | Directory exists, resolver raises a clear typed error (not a silent fallback) if invoked on macOS | Keeps the platform-key space visible per `specs/tech-stack.md`, without pretending macOS is supported before the post-MVP validation pass. |
| Fixture authoring | Fixtures are synthetic and tiny, generated once with the same vendored tools (ExifTool `-GPSLatitude=...` etc. to inject EXIF, FFmpeg `lavfi` sources for the MP4, Pillow + `pillow-heif` for the HEIC), not sourced from any real personal photo | `AGENTS.md` "Tests" — fixtures stay small; mission principle 1 (100% local) and "Testing on real data" — never use the user's real collection. |
| WhatsApp/screenshot fixture names | `IMG-20260730-WA0001.jpg` and `Screenshot_20260730-152000.png` | Exact patterns from README §12/§13 filename regex tables, so later phases' rule tests can reuse these fixtures as positive matches. |
| Fixture without EXIF | Plain JPEG with metadata stripped (`-all=` via ExifTool) | Produces the "JPEG sem EXIF" case from README §30.2 using the same tool already vendored, no extra dependency. |

## Constraints

- **No network at runtime**: the resolver and the app never download a
  binary; vendoring is a one-time authoring step for this phase, exactly
  like `uv sync` in Phase 1. The committed binaries themselves make no
  network calls when invoked.
- **Read-only until Phase 14**: this phase only reads fixtures (or writes
  to fixtures during their one-time authoring); no code path touches a
  user's real files.
- **External tools**: every invocation goes through the resolver and uses
  `subprocess` argument lists — never `shell=True`, never a bare
  `"exiftool"`/`"ffprobe"` string that would fall back to `PATH`.
- **Dependencies**: `pillow-heif` (already pinned in `specs/tech-stack.md`)
  is the only new runtime import this phase needs; no dependency outside
  `specs/tech-stack.md` is added without updating that file first.
- **Language**: all code, comments, config, and commit messages in English.
