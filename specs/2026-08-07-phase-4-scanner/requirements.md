# Requirements — Phase 4: Scanner

## Objective

Recursively walk a user-supplied root folder and persist an inventory of
every media-candidate file — path, size, mtime, and access errors — to
SQLite as a `Scan` and its `MediaFile` rows, without reading file content,
extracting metadata, or writing anything to the source tree. This is the
first half of README's Fase 1 (US-001): discovery only. Type detection
(§6.4, Phase 5) and metadata extraction (§8, Phase 6) build on top of the
rows this phase creates.

## Scope

### In

- Recursive `pathlib` walk from a root path, with a `recursive: bool` flag
  matching the `Scan.recursive` column already in the schema.
- Ignore patterns covering both platform families: `Thumbs.db`,
  `desktop.ini`, `*.tmp`, `.DS_Store`, `._*`, `.Spotlight-V100`, `.Trashes`,
  `.fseventsd`, plus the README §7.1 examples (`~$*`, `*.partial`).
- No symlink following (files or directories).
- Batched processing with a progress callback (file count / bytes so far) —
  the mechanism a future CLI (Phase 7) will render, not a CLI itself.
- Per-entry access errors (permission denied, broken entry, race with
  deletion) recorded on the `MediaFile` row (`processing_status="error"`)
  instead of aborting the scan.
- Size and modification time capture for every discovered file.
- Total file count and total bytes rolled up onto the `Scan` row.
- Path handling: `MediaFile.absolute_path` / `relative_path` stored
  NFC-normalized; every `pathlib`/`os` call uses the OS-native (as-walked)
  form, per `specs/tech-stack.md` "Unicode normalization" (from Phase 4).
- An `exclude_dirs` parameter so the service can be told to skip its own
  report/thumbnail output directories once callers (Phase 7+) know where
  those live (README §7: "avoid accessing its own report and destination
  folders"). No default exclusion list is hardcoded yet since
  `runtime/reports/` locations are per-scan and destinations don't exist
  before Phase 14.

### Out (later phases)

- Media type / content-signature detection (`media_kind`, mismatch
  flagging) — Phase 5.
- ExifTool/FFprobe metadata extraction — Phase 6.
- `media-organizer scan` CLI, JSON export, human-readable progress display
  — Phase 7.
- Any destination/report directory defaults — those paths don't exist
  until later phases wire the CLI.

## Source of truth

- README §7 "Descoberta de arquivos" — scanner responsibilities and default
  ignore list (§7.1).
- README §37 "US-001" — acceptance criteria this phase partially satisfies
  (path validation, subfolder traversal, SQLite persistence, progress,
  error logging, no writes to source files; type detection/metadata/JSON
  export are later phases).
- `specs/roadmap.md` Phase 4 entry and its *Done when* criterion.
- `specs/tech-stack.md` "Cross-platform" table: Unicode normalization and
  Junk files rows, both scoped "From: Phase 4".
- `specs/mission.md` principles 1–3 (offline, read-only until Phase 14,
  never destroy data).
- Existing Phase 3 models/repositories (`backend/app/models/scan.py`,
  `backend/app/models/media_file.py`, `backend/app/repositories/`) — the
  scanner writes through these, no schema changes.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/services/scanner.py` | Matches the planned layout in `AGENTS.md` (`backend/app/{...,services,...}`); first occupant of `services/`. |
| Ignore pattern matching | Combine literal names (`Thumbs.db`, `desktop.ini`) and glob-style patterns (`*.tmp`, `._*`, `~$*`, `*.partial`) plus directory names to prune (`.Spotlight-V100`, `.Trashes`, `.fseventsd`) | Covers README §7.1 and tech-stack's cross-platform junk list in one pass; directory names are pruned from the walk entirely rather than filtered per-file, so their contents are never descended into. |
| Symlinks | `os.walk`/`Path.iterdir` traversal never follows symlinked directories or files; a symlink is recorded as skipped, not as an error | README §7 "não seguir links simbólicos por padrão". |
| Batching | Yield/persist in fixed-size batches (default configurable, e.g. 200 entries) via `MediaFileRepository`, with a progress callback invoked per batch | Matches README §7 "processar em lotes" + "atualizar progresso continuamente" without requiring a UI yet. |
| Unreadable entries | Caught per-entry (`OSError` on `stat()`/`iterdir()`), recorded as a `MediaFile` row with `processing_status="error"` and an error message, scan continues | README §7 "registrar erros de acesso sem interromper todo o processo". |
| NFC normalization | Store `unicodedata.normalize("NFC", ...)` form in `absolute_path`/`relative_path`; keep the as-walked `Path` object (OS-native, possibly NFD) for every filesystem call | `specs/tech-stack.md` rule, `AGENTS.md` "Paths" convention. |
| media_kind / metadata fields | Left unset (`None`) on this phase's rows — populated by Phase 5/6 | Keeps this phase's `MediaFile` writes minimal and avoids guessing at columns those phases own. |
| Scan lifecycle | Service creates the `Scan` row (`status="running"`, `started_at` set) at the start and updates it (`status`, `finished_at`, totals) at the end; caller supplies `source_root` and `recursive` | Matches existing `Scan` columns; no new columns needed. |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): the scanner never
  writes, renames, or deletes anything under the scanned root.
- **100% local and offline** (`specs/mission.md` #1): no network calls;
  this phase doesn't invoke ExifTool/FFmpeg at all, so `resolve_tool` isn't
  involved yet.
- **No bare PATH lookups**: not applicable this phase (no external tool
  invocation), but the module must not introduce one incidentally.
- Paths persisted NFC-normalized, OS-native form used for I/O
  (`specs/tech-stack.md`).
- SQLModel is the only model layer — no parallel Pydantic schemas
  duplicating `Scan`/`MediaFile` (`AGENTS.md`).
