# Requirements — Phase 9: Video + iPhone + RAW rules

## Objective

Implement the first three concrete `ClassificationRule`s against the Phase
8 contract: the video rule (README §9), the iPhone rule (README §10), and
the iPhone RAW rule (README §11) — each unit-tested directly against the
README's own worked cases, no orchestrator/CLI wiring yet (Phase 12).

## Scope

### In

- `VideoRule` (`routing_group = "video"`): fires when `media.mime_type`
  starts with `video/`, or ExifTool's `FileType`/`media.file_type`
  indicates a video container, or `media.media_kind == "video"` (the
  Phase 5/6 pipeline already combined MIME + signature + ExifTool
  `FileType` + FFprobe stream validation into this field — re-deriving
  FFprobe's own process invocation here would duplicate Phase 6, not
  re-implement README §9's rule). A corrupted video
  (`error_code="VIDEO_UNREADABLE"`) still fires — README §9 keeps
  `media_kind: video` for those.
- `IPhoneRule` (`routing_group = "iphone_photo"`): high confidence
  (`score=0.98`) when `Make == "Apple"` and `Model` starts with `"iPhone"`
  (README §10.1, matching §15's own worked example verbatim). For videos
  without a direct Make/Model match, a tiered score from secondary
  QuickTime-adjacent signals (`Software`, `Encoder`/`CompressorName`,
  `HandlerDescription`, `LocationInformation` in ISO 6709 form — README
  §10.2's list, minus GPS coordinates which Phase 11 owns). Never reads
  `media.file_name`/`media.extension` as a positive signal — README §10.3/
  §10.4 are explicit that filename pattern or visual similarity alone must
  not produce a match; an all-metadata-absent case scores `0.0`, well
  under the `confidence <= 0.40` cap §10.3 requires.
- `IPhoneRawRule` (`routing_group = "iphone_raw"`): fires only when the
  file is a DNG (`FileType == "DNG"` or `.dng` extension) **and** the same
  high-confidence Make/Model check as `IPhoneRule` passes — README §11's
  "quando fabricante, modelo e tipo DNG forem conclusivos" describes this
  as one conclusive check, not a dependency on `IPhoneRule`'s own output
  (the `ClassificationRule` protocol gives a rule no access to another
  rule's result). A DNG from a non-Apple camera scores `0.0` (does not
  nominate `iphone_raw`) — combined with Phase 8's resolver, this is what
  makes it fall through to `other`, satisfying the roadmap's "non-Apple
  DNG routes to `other`."
- Unit tests reproducing every worked case in README §9–11 directly
  against each rule's `evaluate()` output.

### Out (later phases)

- WhatsApp/screenshot rules — Phase 10.
- GPS/country fields — Phase 11 (location signals here are limited to
  presence/format, not resolved to a place).
- Wiring rules into an orchestrator, a `Classification` row, or a CLI
  command — Phase 12. No rule here writes to the `Classification` table.
- Non-Apple RAW handling beyond "doesn't nominate `iphone_raw`" — README
  §11's `image_format=raw`/`source_origin=other_camera` fields belong to
  the result-assembly step Phase 12 builds, not to this rule's own output.

## Source of truth

- README §9 "Regras para identificar vídeos".
- README §10 "Regras para identificar conteúdo produzido por iPhone"
  (§10.1–§10.4).
- README §11 "Regras para separar RAW de iPhone".
- README §15 "Motor de classificação" — the `RuleResult`/reasons shape
  these rules must produce (Phase 8 already built the types).
- `specs/roadmap.md` Phase 9 entry and its *Done when* criterion.
- `specs/mission.md` principles 4 (explainable classification), 6
  (deterministic rules first).
- Phase 6's `MediaMetadata`/`metadata.py` — the exact ExifTool field names
  (`Make`, `Model`, `Software`, `Encoder`, `CompressorName`,
  `HandlerDescription`, `LocationInformation`) these rules read from the
  `metadata: dict` parameter.
- Phase 8's `backend/app/rules/engine.py` — the `RuleResult`/
  `ClassificationRule` contract these rules implement.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| `metadata: dict` shape | The raw ExifTool tag subset — the same dict `MediaMetadata.raw_json` already stores (`json.loads(media_metadata.raw_json)`), keyed by README §8.2's exact ExifTool tag names (`Make`, `Model`, `Software`, ...) | The `ClassificationRule` protocol (README §15.1) types `metadata` as a bare `dict`; reusing the Phase 6 raw-subset shape avoids inventing a second normalized vocabulary, and lets reasons quote ExifTool tag names verbatim as README §15's own example does ("EXIF Make=Apple"). |
| Video signal source | `media.mime_type`, `media.file_type` (both already ExifTool-corrected by Phase 6), and `media.media_kind` — no direct FFprobe re-invocation | README §9 lists MIME/ExifTool/FFprobe as the three signals, but Phase 5+6 already combined exactly those into `media.media_kind`/`file_type`/`mime_type`; re-running FFprobe inside a classification rule would duplicate Phase 6 and violate "core before interface" — the rule reads the pipeline's own output. |
| iPhone rule secondary-signal tiers | No direct Make/Model match: 0 secondary Apple signals → `0.0`; 1 → `0.55`; 2 → `0.70`; 3+ → `0.85` (all below the direct-match `0.98`) | README §10.2 only says confidence should scale with "quantidade de sinais encontrados" without fixed numbers; a small monotonic ladder keeps the rule deterministic and testable without pretending to a precision README doesn't specify. |
| iPhone rule secondary signals | `Software` mentions "iPhone"/"iOS"; `Encoder` or `CompressorName` mentions "Apple"; `HandlerDescription` mentions "Apple"/"Core Media"; `LocationInformation` present and shaped like ISO 6709 (`^[+-]\d+(\.\d+)?[+-]\d+(\.\d+)?` — sign-prefixed lat/long pair) | Directly the "fabricante; modelo; software; encoder; chaves Apple; localização no formato ISO 6709" list in README §10.2, minus manufacturer/model (already the direct-match branch) and minus raw GPS lat/long (Phase 11's domain — only the *format* of `LocationInformation` is checked here, not its value). |
| iPhone RAW rule independence | Re-checks Make/Model itself rather than depending on `IPhoneRule`'s result | The `ClassificationRule` protocol gives a rule only `(media, metadata)` — no channel to read another rule's output — and README §11's own wording ("quando fabricante, modelo e tipo DNG forem conclusivos") already describes one self-contained conclusive check, not a two-step dependency. |
| Non-Apple DNG | `IPhoneRawRule` scores it `0.0` (doesn't nominate `iphone_raw`); nothing else claims it either, so Phase 8's resolver falls through to `other` | Matches the roadmap wording exactly; `image_format=raw` / `source_origin=other_camera` (README §11) are `ClassificationResult`-assembly fields, out of scope until Phase 12 builds the orchestrator. |

## Constraints

- **Explainable classification** (`specs/mission.md` #4): every `RuleResult`
  — including score-`0.0` non-matches — carries a specific reason, never an
  empty list.
- **Deterministic rules first** (`specs/mission.md` #6): fixed field checks
  and a fixed scoring ladder; no fuzzy/ML matching.
- README §10.3/§10.4: `IPhoneRule` never uses `media.file_name` or
  `media.extension` as a positive signal for `iphone_camera`.
- SQLModel/DB is untouched by this phase — rules are pure functions over
  `(MediaFile, dict)`.
