# Roadmap

High-level implementation order in very small phases. Each phase is intentionally tiny — roughly a day or less of work — ends in a verifiable state, and builds only on completed phases. Phases map to the README's Fases 0–5; Tauri packaging and local AI are horizon items.

Guiding rule: **the engine is read-only until Phase 14.** No code that moves, renames, or deletes user files exists before the move planner is complete and tested.

## Stage A — Foundation (README Fase 0)

- [x] **Phase 1 — Repo bootstrap.** `pyproject.toml` with uv, Python 3.13, ruff, mypy, pytest, pre-commit; package skeleton `backend/app/`; one trivial passing test. *Done when `uv run pytest` and lint pass clean.*
- [x] **Phase 2 — Tooling + fixtures.** Vendor/locate ExifTool and FFmpeg under per-platform directories (`tools/exiftool/<platform>/`, `tools/ffmpeg/<platform>/`) behind a single resolver keyed on `sys.platform` + `platform.machine()`; verify invocation via `subprocess` argument lists; create first test fixtures (iPhone JPEG with GPS, HEIC, WhatsApp-named file, screenshot-named PNG, small MP4, JPEG without EXIF). Only the Windows binaries are vendored now — the macOS slot stays empty until post-MVP. *Done when a smoke test runs ExifTool and FFprobe against fixtures through the resolver, never via bare `PATH` lookup.*
- [x] **Phase 3 — Data model + SQLite.** SQLModel models for `Scan` and `MediaFile`; database creation under `runtime/database/`; repository layer with basic CRUD. *Done when models round-trip through SQLite in tests.*

## Stage B — Inventory (README Fase 1, US-001)

- [x] **Phase 4 — Scanner.** Recursive `pathlib` walk: ignore patterns covering both platform families (`Thumbs.db`, `desktop.ini`, `*.tmp`, `.DS_Store`, `._*`, `.Spotlight-V100`, `.Trashes`, `.fseventsd`), no symlink following, batching, access errors recorded without aborting, size/mtime captured. Paths are persisted and compared **NFC-normalized**, while the OS-native form is what reaches every filesystem call. *Done when the scanner inventories a nested fixture tree correctly, including an unreadable entry, an AppleDouble `._*` sidecar that must be skipped, and an NFD-named file that matches its NFC twin.*
- [ ] **Phase 5 — Media type detection.** Combine extension, MIME, file signature into `media_kind` (image/video/unsupported); flag extension/content mismatches. *Done when a misnamed fixture (e.g., MP4 renamed `.jpg`) is detected and flagged.*
- [ ] **Phase 6 — Batch metadata extraction.** ExifTool batch JSON extraction (one process for many files), normalized field mapping (README §8.2), raw JSON subset preserved; FFprobe validation for videos, corrupt videos marked `VIDEO_UNREADABLE`. *Done when fixture metadata persists to SQLite with normalized fields.*
- [ ] **Phase 7 — Scan CLI.** `media-organizer scan <path> --recursive --output <dir>`: wires Phases 4–6 with progress display, error log, and JSON export. *Done when US-001 acceptance criteria pass end to end — inventory produced, zero writes to source files.*

## Stage C — Classification (README Fase 2, US-002)

- [ ] **Phase 8 — Rule engine core.** `ClassificationRule` protocol, `RuleResult` (label, score, reasons), `ClassificationResult`, routing-priority resolver (`video > mobile_screenshot > whatsapp_received > iphone_raw > iphone_photo > other`), `Classification` table. *Done when priority resolution is unit-tested with synthetic rule outputs.*
- [ ] **Phase 9 — Video + iPhone + RAW rules.** Video rule (MIME/ExifTool/FFprobe); iPhone rule (Make/Model, QuickTime keys for video, insufficient-signal cap at 0.40); iPhone RAW rule (DNG + iphone_camera); non-Apple DNG routes to `other`. *Done when README §9–11 cases pass as unit tests.*
- [ ] **Phase 10 — WhatsApp + screenshot rules.** WhatsApp filename regexes, directory signals, `Sent` direction, scoring table (§12.3); screenshot name patterns, medium signals, safety rule, confidence bands (§13.4) with `requires_review`. *Done when README §12–13 cases pass, including the "absent EXIF alone proves nothing" negatives.*
- [ ] **Phase 11 — Offline country resolution.** Bundle `countries.geojson`; GPS extraction from EXIF/XMP/QuickTime/ISO 6709; coordinate validation; Shapely STRtree point-in-polygon → ISO code + name; ocean/no-GPS → `unknown`; coordinates hidden from default output. *Done when Tokyo fixture → `JP` and border/ocean cases behave per §14.*
- [ ] **Phase 12 — Classify CLI + overrides.** `media-organizer classify` over an existing scan; results with confidence and reasons; manual override via CLI recorded as `manual_routing_group` with timestamp. *Done when US-002 acceptance criteria pass.*

## Stage D — Reports (README Fase 3)

- [ ] **Phase 13 — Thumbnails + static reports.** Thumbnail generation (Pillow / pillow-heif / rawpy / FFmpeg frame grab) into a folder relative to the report; Jinja2 `report.html` (fully local assets, basic filters) plus `report.json` and `report.csv`. *Done when the first-delivery checklist (README §43) is met: SQLite + JSON + CSV + HTML + error log, zero source modifications.*

> **Checkpoint: validate the analysis pipeline on a real folder before writing any move code.**

## Stage E — Safe movement (README §16–18, US-003/US-004)

- [ ] **Phase 14 — Destinations + move plan (dry run).** `DestinationRule` and `MovePlan` models; group→folder mapping with destination names sanitized to the portable intersection (no `<>:"/\|?*`, no trailing dot/space, no Windows reserved names); plan generation validating existence, permissions, disk space, name collisions (`collision_policy: error`, case-insensitive on NTFS/exFAT/default-APFS volumes), path length (260-character Windows limit checked at plan time), duplicates, source==destination, post-scan changes. *Done when US-003 passes — a complete plan is produced and nothing is executed — including a case-only collision and an over-length path both reported as plan errors.*
- [ ] **Phase 15 — Transactional executor.** Move journal (`MoveOperation` states `planned → … → completed/failed/skipped/cancelled`); same-volume atomic rename; cross-volume hash→copy-temp→verify→rename→delete-source sequence; journal consulted before any operation (idempotent, resumable). The rename-vs-copy decision goes through one `is_same_volume(a, b)` helper with a per-platform implementation — the executor never inspects drive letters or mount points itself. *Done when temp-dir tests cover rename, simulated cross-volume copy, mid-copy failure, and hash mismatch.*
- [ ] **Phase 16 — Execute/resume CLI + move report.** Explicit confirmation step, per-file progress, cancellation between files, resume of an interrupted run, move report (planned/completed/failed/skipped, volumes, per-file validation). *Done when US-004 passes, including a kill-and-resume test.*

## Stage F — API (README Fase 4)

- [ ] **Phase 17 — FastAPI read layer.** App bound to `127.0.0.1`; scan/file/classification/metadata/thumbnail GET endpoints over existing data. *Done when endpoints serve a completed scan.*
- [ ] **Phase 18 — Jobs + progress.** Background job runner (thread/process + SQLite state, no Celery/Redis); POST scan/classify; SSE progress at `/api/jobs/{job_id}/events`; cancellation. *Done when a scan runs via API with live progress.*
- [ ] **Phase 19 — Plan/execute API.** Destinations PUT, move-plan create/approve, execute, move-run status/cancel, report endpoints. *Done when the full US-001→US-004 flow works over HTTP.*

## Stage G — UI (README Fase 5)

- [ ] **Phase 20 — Frontend scaffold + dashboard.** Next.js + TypeScript + pnpm; scan launch form (path field, backend-validated), progress view via SSE, group totals dashboard. *Done when a scan can be started and watched from the browser.*
- [ ] **Phase 21 — Review UI.** TanStack Table inventory with filters (group, confidence, errors, country), thumbnails, metadata + classification reasons panel, manual override editing. *Done when an override made in the UI persists and is marked manual.*
- [ ] **Phase 22 — Destinations, dry run, execution UI.** Destination mapping form, plan summary with conflicts/alerts, explicit confirmation, execution progress, final move report. *Done when the whole MVP flow completes from the browser — this closes README §31.*

## Horizon (post-MVP, order tentative)

- **macOS validation pass**: vendor the `macos-arm64` binaries, add a `macos-latest` CI runner, build NFD/case-collision fixtures from a real Mac-written volume, and exercise the full US-001→US-004 flow. The core is already written for this (tech-stack "Cross-platform"); this phase is where it stops being an assumption.
- **Tauri packaging** (Fase 6): native folder picker, backend sidecar, installer, offline updates. On macOS this is also where TCC permission prompts for `~/Pictures` and external volumes get handled — a native-app concern the CLI never faces.
- **Golden dataset evaluation** (README §30.4): labeled set, precision/recall per rule, screenshot category tracked separately.
- **Local AI phase** (README §33–35): embeddings + FAISS search first, then selective VLM enrichment, then TensorRT optimization — each gated on the previous being measured.
- Resolve open product questions from README §41 (WhatsApp video grouping, country subfolders, collision suffix policy, copy vs. move, …) after real-world use of the prototype.
