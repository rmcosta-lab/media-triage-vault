# Tech Stack

Decisions are pinned here to avoid re-litigating them during implementation. Alternatives the README left open are resolved in the "Pinned decisions" section.

## Pinned decisions

| Decision | Choice | Rationale |
|---|---|---|
| Python version | **Python 3.13** | Latest stable of the two options in the spec; managed via `uv`. |
| ORM / models | **SQLModel** | One model layer for Pydantic validation + SQLAlchemy persistence; fewer duplicate schemas. |
| CLI framework | **Typer** | Typed, minimal boilerplate, plays well with Pydantic-style code; provides `media-organizer scan ...` UX. |
| Offline geocoding | **Shapely + STRtree** over a bundled `countries.geojson` | No GeoPandas dependency in the MVP; point-in-polygon with a spatial index is sufficient. |
| Hashing | **SHA-256** (`hashlib`) | Per spec; `standard` mode hashes cross-volume copies, `strict` hashes everything. |
| Database | **SQLite** (single file under `runtime/database/`) | Local, transactional journal, resumability, no server. |
| Background jobs | **Simple local queue** (thread/process + SQLite state) | No Celery/Redis in the MVP. |
| Packaging | **No Docker** | Windows volume access, path semantics, and cross-volume moves stay simple. |
| Platform support | **Windows 11 released; macOS best-effort** | Core avoids OS-specific assumptions from Phase 2 on, but only Windows is tested and shipped for the MVP. |

## Cross-platform (best-effort)

macOS is a secondary target: **the code is written to run there, but it is not validated there before the MVP closes.** The rules below are cheap to honour up front and expensive to retrofit once the move journal holds real paths, so they apply from the phase noted — even though nothing macOS-specific is tested yet.

| Concern | Rule | From |
|---|---|---|
| Bundled binaries | `tools/exiftool/<platform>/` (`windows-x64`, `macos-arm64`); a single resolver picks by `sys.platform` + `platform.machine()`. **Interim exception (Phase 2):** FFmpeg/FFprobe are *not* vendored — the ~100-250MB Windows build is too large to commit to git history for the MVP. The resolver discovers them once via `shutil.which` (system-installed, e.g. `winget install Gyan.FFmpeg`) behind the same `resolve_tool()` API, so call sites never hardcode a bare command string. True vendoring (or Git LFS) is revisited when Tauri packaging needs a self-contained sidecar. | Phase 2 |
| Unicode normalization | Filenames reach the app as NFC (NTFS, exFAT) or NFD (HFS+, and anything written by older macOS). Store and compare paths **NFC-normalized**; pass the **OS-native form** to every filesystem call. A collection that crossed platforms will contain both. | Phase 4 |
| Case sensitivity | NTFS, exFAT and default APFS are case-insensitive. Collision detection must treat `Foto.jpg` and `foto.jpg` as colliding on those volumes. | Phase 14 |
| Destination names | Sanitize to the strict intersection: no `<>:"/\|?*`, no trailing dot or space, no Windows reserved names (`CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9`, `LPT1`–`LPT9`). A vault built anywhere must open on Windows. | Phase 14 |
| Path length | Validate at plan time, not at execution: Windows breaks at 260 characters without the `\\?\` prefix; macOS tolerates ~1024. | Phase 14 |
| Junk files | Ignore patterns cover both families: `Thumbs.db`, `desktop.ini`, `*.tmp` and `.DS_Store`, `._*` (AppleDouble sidecars, common on exFAT drives), `.Spotlight-V100`, `.Trashes`, `.fseventsd`. | Phase 4 |
| Volume identity | The rename-vs-copy decision goes through one `is_same_volume(a, b)` helper with a per-platform implementation. The executor never inspects drive letters or mount points directly. | Phase 15 |

Explicitly **not** in scope before the MVP closes: macOS CI runners, macOS fixtures, macOS in any phase's done criteria, and macOS TCC/permission handling (a native Tauri concern, not a CLI one). Extended attributes and Finder tags are accepted losses on any cross-platform move.

## Backend (core engine — Phase A)

- **Python 3.13**, dependency management with **uv** (`pyproject.toml` + `uv.lock`, all versions locked)
- **Typer** — CLI entry point (`media-organizer`)
- **SQLModel** + **SQLite** — persistence and transactional move journal
- **Pydantic** — settings and data validation (via SQLModel)
- **Jinja2** — static HTML report templates (all assets local, no CDN)
- stdlib: `pathlib`, `hashlib`, `shutil`, `subprocess` (argument lists only, never shell strings)

## Metadata and media tools

- **ExifTool** — primary metadata source, invoked in batch with JSON output (`-j`), bundled under `tools/exiftool/`
- **FFprobe / FFmpeg** — video validation, frame extraction, video thumbnails, bundled under `tools/ffmpeg/`
- **Pillow** — standard image handling and thumbnails
- **pillow-heif** — HEIC/HEIF support
- **rawpy** — RAW reading and preview generation

## Offline geography

- **Shapely** (with `STRtree` spatial index)
- Bundled `backend/data/geography/countries.geojson` — ISO code + name lookup via point-in-polygon; no network calls ever

## API layer (Phase B)

- **FastAPI**, bound to `127.0.0.1` only
- Progress via **Server-Sent Events**
- Local API docs (no external assets)

## Frontend (Phase C)

- **Next.js** + **TypeScript** + **React**
- **TanStack Table** — inventory/review grid
- **Zod** — API response validation
- **pnpm** with lockfile

## Desktop (post-MVP)

- **Tauri** — native folder picker, backend sidecar, installer; only after the web flow is validated

## Quality

- **pytest** — unit + integration tests (fixtures in `backend/tests/fixtures/`)
- **ruff** — lint + format
- **mypy** — type checking
- **pre-commit** — hooks for the above
- **Playwright** — E2E once the frontend exists

## Future AI phase (not MVP)

Target hardware: RTX 4090 (24 GB VRAM). PyTorch + CUDA first; TensorRT for RTX after profiling. Embeddings: SigLIP 2 So400m or Qwen3-VL-Embedding-2B, stored in local FAISS. VLM enrichment: Qwen3-VL-2B for bulk, Qwen3-VL-8B (4-bit) selectively. No GPU dependency in the metadata MVP.
