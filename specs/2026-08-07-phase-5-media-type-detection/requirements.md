# Requirements — Phase 5: Media type detection

## Objective

Determine the real media type of every `MediaFile` row a scan produced —
combining extension, MIME type, and file signature (magic bytes) — and
record it as `media_kind` (`image` / `video` / `unsupported`). Flag files
whose extension disagrees with their actual content
(`extension_mismatch`). This is the "detect the real type, don't trust the
extension" half of README §6.4; ExifTool `FileType` and FFprobe validation
(the other two signals README §6.4 lists) are Phase 6.

## Scope

### In

- A pure detection function that, given a file path and its extension,
  reads a small header (no full-file read) and returns: `media_kind`,
  `mime_type`, `extension_mismatch`, and a human-readable reason.
- A fixed, hand-rolled extension→category table covering every extension in
  README §6.1 (standard images), §6.2 (RAW images), §6.3 (videos).
- A fixed, hand-rolled extension→MIME map for the same extensions (not
  `stdlib mimetypes`/OS registry — see Decisions).
- A file-signature (magic-byte) sniffer covering JPEG, PNG, GIF, BMP, WEBP,
  TIFF-based RAW (CR2/NEF/ARW/DNG/ORF/RW2/TIFF), Fujifilm RAF, HEIC/HEIF
  (ISO-BMFF `ftyp` with a HEIC-family brand), MP4/MOV/M4V/3GP (ISO-BMFF
  `ftyp`, other brands), AVI (`RIFF....AVI `), and MKV/WEBM (EBML header).
- A service that runs detection over every `MediaFile` row belonging to a
  scan (`processing_status == "pending"`) and persists `media_kind`,
  `mime_type`, `extension_mismatch` back through `MediaFileRepository`.
- Two new `MediaFile` columns: `media_kind: str | None` and
  `extension_mismatch: bool` (default `False`). Schema picks these up via
  the existing `SQLModel.metadata.create_all` — no migrations framework
  exists yet (`backend/app/core/db.py`).
- A misnamed fixture (video content, `.jpg`/image extension) to exercise the
  roadmap's done criterion.

### Out (later phases)

- ExifTool `FileType` / FFprobe stream inspection as detection signals —
  Phase 6.
- Video-corruption handling (`VIDEO_UNREADABLE`) — Phase 6, needs FFprobe.
- RAW vendor/subtype disambiguation (e.g. distinguishing iPhone RAW from
  other DNG producers, or CR3's ISO-BMFF container from MOV) — Phase 9's
  routing rules; Phase 5 only needs the broad `image`/`video` category.
- CLI wiring / JSON export — Phase 7.

## Source of truth

- README §6 "Tipos de arquivo inicialmente suportados" — the three
  extension lists (§6.1–6.3) this phase's category table is built from.
- README §6.4 "Detecção do tipo real" — combine extension + MIME + file
  signature (+ ExifTool/FFprobe in Phase 6); flag extension/content
  mismatches.
- `specs/roadmap.md` Phase 5 entry and its *Done when* criterion.
- `specs/mission.md` principles 1 (offline), 2 (read-only until Phase 14),
  6 (deterministic rules first).
- Phase 4's scanner and models (`backend/app/services/scanner.py`,
  `backend/app/models/media_file.py`) — this phase reads the rows Phase 4
  wrote and adds columns to the same table.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/services/media_type.py` | Second occupant of `services/`, alongside `scanner.py`; keeps detection logic independent of the walk/persistence loop. |
| MIME source | Hand-rolled fixed dict, not `mimetypes.guess_type` | `mimetypes` reads the Windows registry on top of its built-in table, which is non-deterministic across machines and doesn't know several README extensions (`.heic`, `.dng`, `.cr3`, `.raf`, …) by default. A fixed table keeps detection deterministic and offline (`specs/mission.md` #1, #6) and is trivially testable. |
| Signature scope | Detect broad `image`/`video` category only, not container subtype | RAW vendor and MOV-vs-CR3 disambiguation isn't needed until Phase 9's routing rules; keeping the signature table format-family-level (ISO-BMFF `ftyp`, TIFF, EBML, RIFF, plus simple magic prefixes) keeps it small and covers every §6.1–6.3 extension. |
| Combining signals | Signature is ground truth when recognized; extension is the fallback when the signature is unrecognized or unreadable | Content can't lie about its own format; an unrecognized signature (truncated file, format outside the table) shouldn't discard a known, well-formed extension. |
| `media_kind = unsupported` | When neither signature nor extension resolves to `image`/`video` | Matches the roadmap's three-way enum. |
| `extension_mismatch` | `True` only when both the extension-declared category and the signature-detected category are known and disagree | Avoids false positives when the signature is merely unrecognized (e.g. an obscure RAW variant that isn't in the table but has a correct extension). |
| Persistence granularity | A service iterates `MediaFileRepository.list_by_scan(scan_id)` filtered to `processing_status == "pending"` and updates each row via `repository.update()` | Mirrors the Phase-12-style "operate over an existing scan" shape the roadmap uses later, and leaves rows Phase 4 already marked `error` untouched. |
| Read errors during detection | Caught per-file (`OSError`); row's `media_kind` stays `None`, `error_code="SIGNATURE_READ_ERROR"` recorded, loop continues | Matches Phase 4's "record errors without aborting" convention (README §7); a file readable at scan time can still vanish or become inaccessible before detection runs. |
| Fixture | New `backend/tests/fixtures/misnamed_video_as_jpg.jpg`: `sample_video.mp4`'s bytes saved under a `.jpg` name | Directly exercises the roadmap's stated done criterion ("MP4 renamed `.jpg`"). |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): detection only
  reads a small header from each file; it never writes to the scanned
  tree.
- **100% local and offline** (`specs/mission.md` #1): no network calls, no
  OS registry lookups (see MIME decision above).
- **Deterministic rules first** (`specs/mission.md` #6): fixed tables and
  byte-signature checks only — no heuristics beyond what's specified.
- SQLModel is the only model layer — new columns go on the existing
  `MediaFile` table, no parallel schema.
