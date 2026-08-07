# Requirements — Phase 13: Thumbnails + static reports

## Objective

Turn a scanned-and-classified scan into the first-delivery bundle README
§43 requires: alongside the SQLite database that already exists, produce
`report.json`, `report.csv`, `report.html` (with local thumbnails) and an
error log, without modifying a single source file. This closes Stage D
(README Fase 3) and is the checkpoint the roadmap gates all move-related
work behind ("validate the analysis pipeline on a real folder before
writing any move code").

## Scope

### In

- `backend/app/services/thumbnails.py`: `generate_thumbnail(media_file,
  destination) -> ThumbnailResult` dispatching by `media_kind`/extension —
  Pillow for standard raster images, `pillow-heif` for HEIC/HEIF, `rawpy`
  for RAW/DNG, an FFmpeg frame grab (via the Phase 2 `run_tool` resolver)
  for video. Every failure (corrupt file, unreadable RAW, FFmpeg error) is
  caught per file and recorded, never raised — mirrors the Phase 4/6
  "record the error, keep going" pattern.
- `backend/app/services/reports.py`: `generate_report(session, scan_id,
  output_dir) -> ReportSummary` — builds the thumbnails folder, joins
  `MediaFile` + `MediaMetadata` + `Classification` per file, computes
  group/country totals, and writes `report.json`, `report.csv`,
  `report.html` (Jinja2, fully local assets) plus `errors.log` (reusing
  Phase 7's `write_error_log`) into `output_dir`.
- `backend/app/templates/report.html.jinja`: self-contained HTML —
  inline CSS/JS, no CDN, no remote fonts/images/maps (README §19.4) —
  showing the README §19.2 content list, with client-side filters (group,
  confidence band, has-error, country).
- `media-organizer report --scan-id <id> --output <dir>` CLI command,
  same `--output`/`--database` flag shape as `scan`.
- Unit + integration tests: one thumbnail-generation case per media kind
  present in `backend/tests/fixtures/` (JPEG w/ GPS, HEIC, WhatsApp JPEG,
  screenshot PNG, MP4, no-EXIF JPEG, misnamed video, corrupt video), plus
  a RAW/DNG case exercised against a monkeypatched `rawpy` (no real DNG
  fixture exists — see Decisions) and an explicit corrupt/unreadable-file
  case proving the report still renders without a thumbnail for that row.

### Out (later phases)

- On-demand/API thumbnail endpoint (`GET /api/files/{id}/thumbnail`) —
  Phase 17+, needs FastAPI.
- Move report (README §19.3: planned/completed/failed counts, per-file
  validation result) — Phase 16, after the move executor exists.
- Any FastAPI/SSE surface — Stage F.
- A real DNG fixture with genuine raw pixel data — no local tool in this
  project's dependency set can synthesize a valid DNG; Phase 9 hit the
  same gap for `IPhoneRawRule` and left it as documented, mocked coverage.

## Source of truth

- README §43 "Resultado esperado da primeira entrega" — the six-item
  checklist this phase must satisfy.
- README §19 "Relatórios", specifically §19.1 (files to produce), §19.2
  (HTML content list), §19.4 ("Assets locais" — no external dependency,
  thumbnails in a folder relative to the HTML).
- README §14.4 / §28 — coordinates are never shown in the report by
  default; Phase 7's `_media_metadata_to_dict` already excludes them from
  JSON output and this phase must not reintroduce them via
  `Classification.gps_latitude`/`gps_longitude`.
- `specs/roadmap.md` Phase 13 entry and its *Done when* criterion.
- `specs/tech-stack.md` "Backend" (Jinja2, Pillow, pillow-heif, rawpy) and
  "Metadata and media tools" (FFmpeg frame extraction, video thumbnails).
- `specs/mission.md` principles 1 (100% local/offline — no CDN, no
  external calls), 2 (read-only until Phase 14), 4 (explainable
  classification — confidence + reasons must reach the report).
- Phase 2's `core/tools.py` `run_tool`/`resolve_tool` — the only path
  this phase is allowed to invoke FFmpeg through.
- Phase 7's `cli/scan_report.py` (`write_error_log`,
  `_media_metadata_to_dict`'s coordinate-exclusion precedent) — reused,
  not reimplemented.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/services/thumbnails.py` + `backend/app/services/reports.py`, template at `backend/app/templates/report.html.jinja` | Matches the `services/`/`templates/` split already reserved in AGENTS.md's repository layout; same orchestration shape as `scanner.py`/`metadata.py`/`classification.py`. |
| Thumbnail format/size | JPEG, long edge capped at 320px, quality 82 | Small enough that hundreds of thumbnails stay light for a local HTML file; a preview, not a full-res copy — matches "miniatura" throughout the README. |
| Thumbnail storage | `<output>/thumbnails/<media_file_id>.jpg`, no new DB column | README §19.4 places thumbnails "relative to the HTML", not in the top-level `runtime/thumbnails/` cache reserved for the future on-demand API endpoint (Phase 17+). Filename is deterministic from `MediaFile.id`, so nothing needs to be persisted to look it back up. |
| RAW thumbnail source | `rawpy.imread(path).extract_thumb()` (embedded preview) first, `postprocess()` full-decode fallback only if no usable embedded preview | Avoids a full raw demosaic per file when the camera already embedded a JPEG/bitmap preview — same cost trade-off rawpy's own docs recommend for thumbnailing. |
| HEIC decoding | `pillow_heif.register_heif_opener()` then open via Pillow like any other format | Already the pattern `backend/tests/fixtures/generate_fixtures.py` uses; no second HEIC code path. |
| Video thumbnail | One `run_tool("ffmpeg", [...])` call per video: seek to `00:00:01` (or start, if shorter), grab one frame, scale to the 320px cap via `-vf scale=320:-2`, write JPEG directly | Reuses the Phase 2 resolver as-is; scaling in FFmpeg avoids a second Pillow round-trip for video. |
| Per-file failure handling | `ThumbnailResult(success, error_code, error_message)`; a failing/unsupported file gets no thumbnail and is still listed in the report as "no preview available" | Mirrors Phase 4/6: record and continue, never abort the batch over one bad file. Directly satisfies this phase's "corrupt/unreadable handling" validation criterion. |
| RAW/DNG test coverage | Unit tests monkeypatch `rawpy.imread` for the success path; a real (but content-invalid) file named `*.dng` proves the exception → `ThumbnailResult(success=False)` fallback path | No fixture generator in this repo can produce genuine raw sensor data — same gap Phase 9 documented for `IPhoneRawRule`. Recorded here rather than silently skipped. |
| `report.json` shape | One object per file merging the Phase 7 `MediaFile`/`MediaMetadata` fields (coordinates still excluded) with `Classification`'s effective fields (`effective_routing_group`, `confidence`, `reasons`, `country_code`, `country_name` — not GPS) and a `thumbnail_path` (relative to `report.json`'s own directory, `null` when none), plus a summary block (`generated_at`, `source_root`, `total_files`, `total_bytes`, totals by group, totals by country). | Keeps the JSON self-sufficient for any later consumer (Phase 17's API, a script) without a second DB read, while holding the same "no coordinates" line Phase 7 already drew. |
| `report.csv` shape | One flat row per file: the same fields as `report.json`, reasons joined with `; ` | Matches README §43's "CSV resumido" — a flat summary for spreadsheet triage, not a nested structure. |
| `report.html` filters | Client-side vanilla JS over `data-*` attributes rendered by Jinja2 (group, confidence band, has-error, country) — no server round-trip, no CDN script | README §19.4 explicitly forbids external JS/CDN/remote assets; "basic filters" (roadmap) doesn't require a build step or framework. |
| CLI surface | `media-organizer report --scan-id <id> --output <dir>` (same `--output`/`--database` shape as `scan`); regenerates `errors.log` into the same `--output` via Phase 7's `write_error_log` | One command, pointed at one directory, produces the full README §43 bundle (JSON+CSV+HTML+error log) from an already-scanned-and-classified scan — no need to remember `scan`'s original `--output`. |
| New dependencies | `rawpy` and `Jinja2` added to `pyproject.toml` (both already pinned in `specs/tech-stack.md`); mypy `ignore_missing_imports` override added for `rawpy` (no bundled type stubs) | Both were anticipated by tech-stack from the start; this is the first phase that actually imports them. |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): thumbnail
  generation and report writing only *read* source files and the
  database; every write target is under the caller-supplied `--output`
  directory.
- **100% local and offline** (`specs/mission.md` #1): no CDN, no remote
  font/script/image reference in `report.html`; FFmpeg/ExifTool/rawpy/
  Pillow calls never touch the network.
- **No coordinates in the report by default** (README §14.4/§28): only
  `country_code`/`country_name` reach `report.json`/`.csv`/`.html` —
  never `gps_latitude`/`gps_longitude`.
- **Explainable classification** (`specs/mission.md` #4): every file row
  in the report carries its `effective_routing_group`, `confidence`, and
  `reasons`, plus a manual-override marker when one exists.
- **External tools through the resolver only**: the video thumbnail path
  calls `run_tool("ffmpeg", [...])` — never a bare `ffmpeg` string.
