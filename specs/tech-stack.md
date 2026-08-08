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
- **Uvicorn** — the local ASGI server FastAPI runs on; `media-organizer
  serve` hardcodes `host="127.0.0.1"` with no `--host` override
- Progress via **Server-Sent Events**
- Local API docs: FastAPI's default `/docs`/`/redoc` load their JS/CSS
  from a CDN, which principle 1's "no CDN assets" forbids, so both are
  disabled (`docs_url=None`, `redoc_url=None`); `/openapi.json` stays on
  (generated in-process, no network) for tooling
- **httpx** (dev only) — required by `fastapi.testclient.TestClient`

## Frontend (Phase C)

- **Next.js** (App Router) + **TypeScript** + **React**, no Tailwind/UI
  library pinned — plain CSS Modules until a phase actually needs one
- **TanStack Table** — inventory/review grid (Phase 21). The installed
  version (9.x) uses a redesigned API (`useTable`/`tableFeatures`/
  `createColumnHelper`/`table.FlexRender`) that is a hard break from the
  commonly-known v8 API (`useReactTable`/`getCoreRowModel`/`flexRender`)
  — read `node_modules/@tanstack/*/skills/*/SKILL.md` (bundled with the
  package) before writing table code in a later phase
- **Zod** — API response validation, parsed at the API-client boundary
  (`frontend/lib/api.ts`)
- **pnpm** with lockfile
- Progress: the browser's native `EventSource` against the backend's
  SSE endpoints (Phase 18) — no extra dependency
- CORS: the API allows only `localhost`/`127.0.0.1` origins (any port,
  via `allow_origin_regex`) — required because the browser enforces
  CORS across ports even when both ends are local (Phase 20)

## Desktop (post-MVP)

- **Tauri** — native folder picker, backend sidecar, installer; only after the web flow is validated

## Quality

- **pytest** — unit + integration tests (fixtures in `backend/tests/fixtures/`)
- **ruff** — lint + format
- **mypy** — type checking
- **pre-commit** — hooks for the above
- **Playwright** — E2E once the frontend exists

## Local AI (Stage H, post-MVP)

- **Installation:** PyTorch, Transformers, Accelerate, and their model-runtime
  dependencies live in the optional `ai` project extra. The base application,
  metadata pipeline, and normal test suite never require PyTorch or a GPU.
- **Model supply:** model weights are user-supplied directories outside the
  repository. The application never downloads or resolves a remote model ID:
  every Transformers load uses a local path plus `local_files_only=True`, with
  Hugging Face/Transformers offline environment flags set before the libraries
  are imported.
- **Bulk image model:** `google/siglip2-so400m-patch14-384` for zero-shot theme
  scoring and optional embeddings. Scores are relative similarities until a
  Phase 26 calibration profile turns score/margin bands into accept/ambiguous/
  review decisions.
- **Selective VLM:** `Qwen/Qwen3-VL-4B-Instruct`, restricted to validated JSON
  over the run's taxonomy. It runs automatically only for ambiguous CUDA cases;
  CPU use requires an explicit command and a latency warning.
- **Licensing/revisions:** the selected [SigLIP 2](https://huggingface.co/google/siglip2-so400m-patch14-384)
  and [Qwen3-VL-4B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct)
  model cards declare Apache-2.0. Phase 23 records the exact local snapshot
  revision/fingerprint and rechecks its license before the runtime is accepted.
- **Hardware:** CPU and NVIDIA CUDA are supported. `auto` prefers CUDA when
  available; conservative device-specific batch defaults may be overridden.
  Models are unloaded between cascade stages. The primary validation target is
  Windows 11 with an RTX 4090, plus a forced-CPU real-model pass.
- **Persistence:** themes and audit fields remain in SQLite. Embeddings are
  optional (enabled by default), stored under `runtime/embeddings/`, and keyed
  by content/model/preprocessor fingerprints; FAISS is not part of Stage H.
- **Optimization:** PyTorch is the only Stage H inference backend. Throughput,
  RAM, and VRAM are measured, but TensorRT is a later horizon item gated on the
  profile showing a worthwhile bottleneck.
- **Explicit exclusions:** Stage H does not include semantic search, FAISS,
  Florence-2/OCR/captions, video inference, or face clustering/recognition.
