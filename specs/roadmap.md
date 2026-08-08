# Roadmap

High-level implementation order in very small phases. Each phase is intentionally tiny — roughly a day or less of work — ends in a verifiable state, and builds only on completed phases. Phases 1–22 map to the README's Fases 0–5; Stage H begins the post-MVP local-AI work described in `README_models.md`.

Guiding rule: **the engine is read-only until Phase 14.** No code that moves, renames, or deletes user files exists before the move planner is complete and tested.

## Stage A — Foundation (README Fase 0)

- [x] **Phase 1 — Repo bootstrap.** `pyproject.toml` with uv, Python 3.13, ruff, mypy, pytest, pre-commit; package skeleton `backend/app/`; one trivial passing test. *Done when `uv run pytest` and lint pass clean.*
- [x] **Phase 2 — Tooling + fixtures.** Vendor/locate ExifTool and FFmpeg under per-platform directories (`tools/exiftool/<platform>/`, `tools/ffmpeg/<platform>/`) behind a single resolver keyed on `sys.platform` + `platform.machine()`; verify invocation via `subprocess` argument lists; create first test fixtures (iPhone JPEG with GPS, HEIC, WhatsApp-named file, screenshot-named PNG, small MP4, JPEG without EXIF). Only the Windows binaries are vendored now — the macOS slot stays empty until post-MVP. *Done when a smoke test runs ExifTool and FFprobe against fixtures through the resolver, never via bare `PATH` lookup.*
- [x] **Phase 3 — Data model + SQLite.** SQLModel models for `Scan` and `MediaFile`; database creation under `runtime/database/`; repository layer with basic CRUD. *Done when models round-trip through SQLite in tests.*

## Stage B — Inventory (README Fase 1, US-001)

- [x] **Phase 4 — Scanner.** Recursive `pathlib` walk: ignore patterns covering both platform families (`Thumbs.db`, `desktop.ini`, `*.tmp`, `.DS_Store`, `._*`, `.Spotlight-V100`, `.Trashes`, `.fseventsd`), no symlink following, batching, access errors recorded without aborting, size/mtime captured. Paths are persisted and compared **NFC-normalized**, while the OS-native form is what reaches every filesystem call. *Done when the scanner inventories a nested fixture tree correctly, including an unreadable entry, an AppleDouble `._*` sidecar that must be skipped, and an NFD-named file that matches its NFC twin.*
- [x] **Phase 5 — Media type detection.** Combine extension, MIME, file signature into `media_kind` (image/video/unsupported); flag extension/content mismatches. *Done when a misnamed fixture (e.g., MP4 renamed `.jpg`) is detected and flagged.*
- [x] **Phase 6 — Batch metadata extraction.** ExifTool batch JSON extraction (one process for many files), normalized field mapping (README §8.2), raw JSON subset preserved; FFprobe validation for videos, corrupt videos marked `VIDEO_UNREADABLE`. *Done when fixture metadata persists to SQLite with normalized fields.*
- [x] **Phase 7 — Scan CLI.** `media-organizer scan <path> --recursive --output <dir>`: wires Phases 4–6 with progress display, error log, and JSON export. *Done when US-001 acceptance criteria pass end to end — inventory produced, zero writes to source files.*

## Stage C — Classification (README Fase 2, US-002)

- [x] **Phase 8 — Rule engine core.** `ClassificationRule` protocol, `RuleResult` (label, score, reasons), `ClassificationResult`, routing-priority resolver (`video > mobile_screenshot > whatsapp_received > iphone_raw > iphone_photo > other`), `Classification` table. *Done when priority resolution is unit-tested with synthetic rule outputs.*
- [x] **Phase 9 — Video + iPhone + RAW rules.** Video rule (MIME/ExifTool/FFprobe); iPhone rule (Make/Model, QuickTime keys for video, insufficient-signal cap at 0.40); iPhone RAW rule (DNG + iphone_camera); non-Apple DNG routes to `other`. *Done when README §9–11 cases pass as unit tests.*
- [x] **Phase 10 — WhatsApp + screenshot rules.** WhatsApp filename regexes, directory signals, `Sent` direction, scoring table (§12.3); screenshot name patterns, medium signals, safety rule, confidence bands (§13.4) with `requires_review`. *Done when README §12–13 cases pass, including the "absent EXIF alone proves nothing" negatives.*
- [x] **Phase 11 — Offline country resolution.** Bundle `countries.geojson`; GPS extraction from EXIF/XMP/QuickTime/ISO 6709; coordinate validation; Shapely STRtree point-in-polygon → ISO code + name; ocean/no-GPS → `unknown`; coordinates hidden from default output. *Done when Tokyo fixture → `JP` and border/ocean cases behave per §14.*
- [x] **Phase 12 — Classify CLI + overrides.** `media-organizer classify` over an existing scan; results with confidence and reasons; manual override via CLI recorded as `manual_routing_group` with timestamp. *Done when US-002 acceptance criteria pass.*

## Stage D — Reports (README Fase 3)

- [x] **Phase 13 — Thumbnails + static reports.** Thumbnail generation (Pillow / pillow-heif / rawpy / FFmpeg frame grab) into a folder relative to the report; Jinja2 `report.html` (fully local assets, basic filters) plus `report.json` and `report.csv`. *Done when the first-delivery checklist (README §43) is met: SQLite + JSON + CSV + HTML + error log, zero source modifications.*

> **Checkpoint: validate the analysis pipeline on a real folder before writing any move code.**

## Stage E — Safe movement (README §16–18, US-003/US-004)

- [x] **Phase 14 — Destinations + move plan (dry run).** `DestinationRule` and `MovePlan` models; group→root mapping with the sanitized group name automatically appended as a destination subfolder (before the optional country subfolder); destination names sanitized to the portable intersection (no `<>:"/\|?*`, no trailing dot/space, no Windows reserved names); plan generation validating existence, permissions, disk space, name collisions (`collision_policy: error`, case-insensitive on NTFS/exFAT/default-APFS volumes), path length (260-character Windows limit checked at plan time), duplicates, source==destination, post-scan changes. *Done when US-003 passes — a complete plan is produced and nothing is executed — including a case-only collision and an over-length path both reported as plan errors.*
- [x] **Phase 15 — Transactional executor.** Move journal (`MoveOperation` states `planned → … → completed/failed/skipped/cancelled`); same-volume atomic rename; cross-volume hash→copy-temp→verify→rename→delete-source sequence; journal consulted before any operation (idempotent, resumable). The rename-vs-copy decision goes through one `is_same_volume(a, b)` helper with a per-platform implementation — the executor never inspects drive letters or mount points itself. *Done when temp-dir tests cover rename, simulated cross-volume copy, mid-copy failure, and hash mismatch.*
- [x] **Phase 16 — Execute/resume CLI + move report.** Explicit confirmation step, per-file progress, cancellation between files, resume of an interrupted run, move report (planned/completed/failed/skipped, volumes, per-file validation). *Done when US-004 passes, including a kill-and-resume test.*

## Stage F — API (README Fase 4)

- [x] **Phase 17 — FastAPI read layer.** App bound to `127.0.0.1`; scan/file/classification/metadata/thumbnail GET endpoints over existing data. *Done when endpoints serve a completed scan.*
- [x] **Phase 18 — Jobs + progress.** Background job runner (thread/process + SQLite state, no Celery/Redis); POST scan/classify; SSE progress at `/api/jobs/{job_id}/events`; cancellation. *Done when a scan runs via API with live progress.*
- [x] **Phase 19 — Plan/execute API.** Destinations PUT, move-plan create/approve, execute, move-run status/cancel, report endpoints. *Done when the full US-001→US-004 flow works over HTTP.*

## Stage G — UI (README Fase 5)

- [x] **Phase 20 — Frontend scaffold + dashboard.** Next.js + TypeScript + pnpm; scan launch form (path field, backend-validated), progress view via SSE, group totals dashboard. *Done when a scan can be started and watched from the browser.*
- [x] **Phase 21 — Review UI.** TanStack Table inventory with filters (group, confidence, errors, country), thumbnails, metadata + classification reasons panel, manual override editing. *Done when an override made in the UI persists and is marked manual.*
- [x] **Phase 22 — Destinations, dry run, execution UI.** Destination mapping form, plan summary with conflicts/alerts, explicit confirmation, execution progress, final move report. *Done when the whole MVP flow completes from the browser — this closes README §31.*

## Stage H — Selective local AI (post-MVP, `README_models.md` §§5–10)

- [ ] **Phase 23 — Offline AI runtime.** Add an optional `ai` dependency extra; persist local SigLIP 2 and Qwen3-VL model paths plus device/batch preferences; detect CPU/CUDA; choose conservative automatic profiles with an advanced override; force Transformers offline mode and local-only model loading. *Done when the diagnostic loads SigLIP 2 from a configured local directory on both CPU and the RTX 4090 without attempting any network access.*
- [ ] **Phase 24 — Multi-root AI runs.** Add `AiRun`/`AiRunSource` around one normal `Scan` per independently selected root; allow per-root recursion; automatically run the complete technical scan/type/metadata/classification pipeline; hash files with SHA-256; mark videos not applicable; persist per-file progress so cancellation and resume skip compatible completed work. *Done when one AI run inventories two independent roots without modifying either source tree and resumes after cancellation without repeating completed files.*
- [ ] **Phase 25 — SigLIP 2 theme classification.** Run `google/siglip2-so400m-patch14-384` over eligible images; provide an editable global taxonomy with stable IDs and PT-BR labels; snapshot the taxonomy per run; persist automatic/effective themes, secondary themes, relative scores, method, reasons, and review state; optionally persist embeddings under `runtime/embeddings/` (enabled by default); reuse only fingerprint-compatible artifacts. *Done when real-model CPU and CUDA runs persist explainable theme results and a repeated compatible run reuses cached work.*
- [ ] **Phase 26 — Golden dataset + calibration.** Add a local, unversioned manifest and evaluation harness for approximately 1,000 user-labeled images; split duplicate-safe calibration/test sets; calibrate top-1 score and top-1/top-2 margin; report macro-F1, per-theme recall, throughput, RAM, and VRAM. *Done when the held-out test set reaches macro-F1 ≥ 0.80 and recall ≥ 0.65 for every theme on the calibrated automatic-accept path; performance is recorded but is not a release gate.*
- [ ] **Phase 27 — Selective Qwen cascade.** Use local `Qwen/Qwen3-VL-4B-Instruct` only for calibrated ambiguous cases; run it automatically on CUDA and only by explicit command with a latency warning on CPU; validate taxonomy-constrained JSON; unload models between stages; map valid but unresolved outputs to `other` while preserving technical failures as errors. *Done when ambiguous fixtures follow the correct SigLIP→Qwen/manual path, out-of-taxonomy output is rejected, and no model stays resident unnecessarily.*
- [ ] **Phase 28 — Local AI CLI + API.** Complete the Typer surface begun by Phase 23 with analyze, resume, evaluate, and manual-Qwen commands; expose local-AI settings, run creation/status/results, cancel/resume, overrides, and Qwen routes; reuse the existing job SSE stream; return explicit errors for missing extras, weights, or devices. *Done when a multi-root run can be configured, launched, cancelled, resumed, and reviewed through both CLI and HTTP.*
- [ ] **Phase 29 — AI configuration + run UI.** Add a Local AI page with multiple absolute-path inputs, recursion per root, model/device status, advanced batch controls, editable taxonomy, embedding storage/space estimate, stage progress, errors, cancellation, and resume. *Done when a two-root run can be started and watched to completion in a real browser.*
- [ ] **Phase 30 — Theme review UI.** Filter AI results by theme, method, source, review state, and error; show scores/reasons; edit the main and secondary themes while preserving automatic/manual/effective values separately. *Done when a manual theme correction survives reload and leaves the technical `routing_group` unchanged.*
- [ ] **Phase 31 — Destination suggestions.** Configure a destination root; suggest portable `theme_id` subfolders from the effective main theme; approve in bulk per theme with per-file exclusions/corrections; ignore secondary themes for routing; persist decisions without creating or executing a move plan. *Done when reviewed suggestions and exceptions round-trip without any filesystem move or `MovePlan` creation.*
- [ ] **Phase 32 — Safe-move integration for AI decisions.** Convert approved AI destination decisions into the existing `MovePlan`/`MoveOperation` workflow using `destination_root / theme_id / [country] / original_file_name`; retain every existing validation, dry run, explicit approval, transactional execution, and report guarantee. *Done when selection → technical pipeline → AI → review → destination approval → dry run → plan approval → execution → report completes end to end without bypassing a safety gate.*

## Horizon (post-MVP, order tentative)

- **macOS validation pass**: vendor the `macos-arm64` binaries, add a `macos-latest` CI runner, build NFD/case-collision fixtures from a real Mac-written volume, and exercise the full US-001→US-004 flow. The core is already written for this (tech-stack "Cross-platform"); this phase is where it stops being an assumption.
- **Tauri packaging** (Fase 6): native folder picker, backend sidecar, installer, offline updates. On macOS this is also where TCC permission prompts for `~/Pictures` and external volumes get handled — a native-app concern the CLI never faces.
- **Deterministic-rule golden dataset** (README §30.4): precision/recall per metadata rule, with screenshot tracked separately from Stage H's semantic-theme evaluation.
- **Semantic search + FAISS**: index the optional Stage H embeddings only after theme classification and cache behavior are measured on the real library.
- **Florence-2 enrichment**: OCR and captions remain separate from theme classification.
- **Video AI**: representative-frame or temporal sampling requires its own measured design.
- **TensorRT optimization**: only after the PyTorch CPU/CUDA profiles show a justified bottleneck.
- **Local face clustering**: biometric-data phase for local similarity grouping and user-supplied names only; no external identity discovery.
- Resolve open product questions from README §41 (WhatsApp video grouping, country subfolders, collision suffix policy, copy vs. move, …) after real-world use of the prototype.
