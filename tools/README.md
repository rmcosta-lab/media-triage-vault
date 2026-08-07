# Vendored tools

## ExifTool

Vendored under `exiftool/windows-x64/` — the official standalone Windows
executable package (ExifTool 13.59, Phil Harvey, exiftool.org via
SourceForge). `exiftool.exe` is a small wrapper that depends on the
sibling `exiftool_files/` directory (bundled Perl runtime); both must ship
together. Upstream license is at
`exiftool/windows-x64/exiftool_files/LICENSE`.

`exiftool/macos-arm64/` is an empty slot — vendoring for macOS is a
post-MVP item (see `specs/roadmap.md` "Horizon").

To upgrade: download the "Windows Executable" zip from
<https://exiftool.org/>, replace `exiftool.exe` and `exiftool_files/`
wholesale, update the version noted here.

## FFmpeg / FFprobe

**Not vendored.** The official Windows build is ~100-250 MB, too large to
commit to git history for the MVP (see `specs/tech-stack.md` "Bundled
binaries" and `AGENTS.md` "Implementation conventions" for the full
rationale). `backend/app/core/tools.py` resolves `ffmpeg`/`ffprobe` from
the system installation via a single, centralized `shutil.which()` call —
install with `winget install Gyan.FFmpeg` (or any FFmpeg build that puts
`ffmpeg`/`ffprobe` on `PATH`).

This is revisited (real vendoring or Git LFS) when Tauri packaging needs a
self-contained sidecar.
