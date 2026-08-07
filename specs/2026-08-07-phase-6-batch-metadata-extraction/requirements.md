# Requirements — Phase 6: Batch metadata extraction

## Objective

Extract the README §8.2 metadata field set for every pending `MediaFile` row
of a scan using **one batched ExifTool process for many files** (never one
process per file), normalize the result into typed columns, and preserve a
JSON subset for audit. For rows Phase 5 marked `media_kind="video"`, run
FFprobe to confirm the file actually has a readable video stream; a video
that fails this check stays `media_kind: video` but is marked
`processing_status: error`, `error_code: VIDEO_UNREADABLE` (README §9).

## Scope

### In

- A fixed field list matching README §8.2 exactly, passed to ExifTool as
  explicit `-TagName` arguments (not a bare `-j` dump) so batch output
  stays small and deterministic.
- One `run_tool("exiftool", ["-j", "-n", *tag_args, *paths])` call per batch
  of pending, non-`unsupported` `MediaFile` rows (batch size matches the
  scanner's existing `DEFAULT_BATCH_SIZE = 200` convention), never one
  process per file.
- Normalized fields persisted to a new `MediaMetadata` table (one row per
  `MediaFile`, FK `media_file_id`): capture datetime (first of
  `DateTimeOriginal` / `CreateDate` / `MediaCreateDate` / `TrackCreateDate`
  that parses), `make`, `model`, `software`, `lens_model`,
  `camera_serial_number`, `gps_latitude`, `gps_longitude`,
  `gps_position_raw`, `location_information`, `handler_description`,
  `compressor_name`, `encoder`, `rotation`, `profile_description`,
  `color_space`, plus `raw_json` (the README §8.2 subset ExifTool actually
  returned for that file, for audit).
- Existing `MediaFile` columns (`file_type`, `mime_type`, `width`, `height`,
  `duration_seconds`) are updated from ExifTool's `FileType`, `MIMEType`,
  `ImageWidth`, `ImageHeight`, `Duration` when present — ExifTool is a
  stronger signal than Phase 5's extension/signature guess.
- FFprobe stream validation for every row with `media_kind == "video"`:
  `-show_streams`, JSON output; at least one `codec_type == "video"` stream
  required. A non-zero exit, unparsable JSON, or no video stream marks the
  row `VIDEO_UNREADABLE` per README §9's exact fields.
- A corrupt-video fixture (a truncated MP4) to exercise the
  `VIDEO_UNREADABLE` path.
- A service, `extract_metadata_for_scan`, that operates over an existing
  scan's rows (mirrors Phase 5's `detect_media_types_for_scan` shape) and
  returns a summary of counts.

### Out (later phases)

- CLI wiring / progress display / JSON export — Phase 7.
- Using metadata fields for classification (`Make`/`Model` routing, GPS →
  country) — Phases 9–11.
- Thumbnail/preview generation (Pillow/rawpy/FFmpeg frame grab) — Phase 13.

## Source of truth

- README §8 "Extração de metadados" (§8.1 batch ExifTool, §8.2 the exact
  field list, §8.3 complementary tools) — this phase's normalized field set
  and batching requirement.
- README §9 "Regras para identificar vídeos" — the exact
  `media_kind`/`processing_status`/`error_code` triple for a corrupt video.
- `specs/roadmap.md` Phase 6 entry and its *Done when* criterion.
- `specs/mission.md` principles 1 (offline), 2 (read-only until Phase 14),
  6 (deterministic rules first).
- Phase 5's `backend/app/services/media_type.py` and
  `backend/app/models/media_file.py` — this phase reads the `media_kind`
  Phase 5 wrote and extends the same rows.
- `backend/app/core/tools.py` — the only allowed way to invoke ExifTool/FFprobe.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/services/metadata.py` | Third occupant of `services/`, same shape as `scanner.py`/`media_type.py`. |
| Normalized storage | New `MediaMetadata` table, not more columns on `MediaFile` | README §8.2 lists ~20 fields beyond what `MediaFile` already carries (`file_type`, `mime_type`, `width`, `height`, `duration_seconds` stay there since Phase 3/5 own them); a dedicated one-to-one table keeps `MediaFile` from becoming a 30-column dumping ground and matches "multidimensional" modeling (`specs/mission.md` #5). |
| ExifTool invocation | Explicit `-TagName` args (the README §8.2 list) + `-j -n`, one process per batch of paths | `-j` for JSON, `-n` for numeric/machine-readable output (decimal GPS degrees, numeric `Duration`/`Rotation`) so no human-format parsing is needed; explicit tags avoid pulling large embedded thumbnails/binary blobs into every batch. |
| Batch size | 200, same constant convention as `scanner.py`'s `DEFAULT_BATCH_SIZE` | Keeps the OS command-line length bounded and mirrors the existing scanning batch shape; not configurable beyond a keyword default for this phase. |
| Row↔result matching | Positional: ExifTool preserves argument order in its JSON array output | Simpler than matching on `SourceFile` string normalization across OS path separators/case; documented ExifTool behavior for `-j` batches. |
| Capture datetime priority | `DateTimeOriginal` → `CreateDate` → `MediaCreateDate` → `TrackCreateDate`, first that parses | `DateTimeOriginal` is the most reliable "when the shutter opened" field for photos; video containers only carry the `MediaCreateDate`/`TrackCreateDate` QuickTime pair. |
| `MediaFile.file_type`/`mime_type`/`width`/`height`/`duration_seconds` | Overwritten by ExifTool's `FileType`/`MIMEType`/`ImageWidth`/`ImageHeight`/`Duration` when ExifTool returns a value | ExifTool parses the actual container/codec, a stronger signal than Phase 5's extension/signature guess (README §6.4 lists ExifTool `FileType` as a detection signal alongside extension/MIME/signature). |
| Per-file ExifTool error | Entry contains an `"Error"` key (e.g. unreadable file) → `MediaMetadata` row still created with all fields `None` except `raw_json`; `MediaFile.error_code = "METADATA_READ_ERROR"` recorded, loop continues | Matches the Phase 4/5 "record errors without aborting" convention (README §7). |
| FFprobe invocation | One process per video row (`-show_streams -print_format json`), not batched | FFprobe has no multi-file batch JSON mode; only rows already flagged `media_kind == "video"` by Phase 5 pay this cost. |
| `VIDEO_UNREADABLE` fields | Exactly `media_kind: video`, `processing_status: error`, `error_code: VIDEO_UNREADABLE` per README §9 — `media_kind` is never cleared | The file is still known to be video content; only its readability failed. |
| Fixture | New `backend/tests/fixtures/corrupt_video.mp4`: first 256 bytes of `sample_video.mp4`, truncated mid-stream | Produces a file FFprobe cannot find a valid video stream in, while still extension/signature-detected as `video` by Phase 5's logic. |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): ExifTool/FFprobe are
  invoked in read-only modes only (`-j`, `-show_streams`); no `-overwrite_original`
  or similar write flags are ever used outside the fixture generator.
- **100% local and offline** (`specs/mission.md` #1): no network calls.
- **External tools only via the resolver** (`AGENTS.md`): every invocation
  goes through `run_tool`, argument lists only, never a shell string.
- **Deterministic rules first** (`specs/mission.md` #6): field mapping is a
  fixed table, no heuristics beyond the priority order above.
- SQLModel is the only model layer; the new `MediaMetadata` table follows
  the `Relationship()`/quoted-forward-ref convention already used by
  `Scan`/`MediaFile` (`AGENTS.md` "Types").
