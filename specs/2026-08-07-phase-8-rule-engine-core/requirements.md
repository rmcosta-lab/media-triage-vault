# Requirements — Phase 8: Rule engine core

## Objective

Build the classification engine's shared scaffolding — the `ClassificationRule`
protocol, `RuleResult`/`ClassificationResult` shapes, the routing-priority
resolver, and the `Classification` table — so Phases 9–10 only have to add
concrete rules against an already-tested contract. No concrete rule (video,
iPhone, RAW, WhatsApp, screenshot) is implemented in this phase.

## Scope

### In

- `RuleResult` (README §15: `label`, `score`, `reasons`) — the per-rule
  output shape.
- `ClassificationRule` protocol (README §15.1: `name: str`,
  `evaluate(media: MediaFile, metadata: dict) -> RuleResult`).
- `ClassificationResult` (README §15.2: `media_kind`, `source_origin`,
  `image_format`, `routing_group`, `confidence`, `reasons`,
  `requires_review`) — the assembled, final-for-this-file shape.
- `ROUTING_GROUPS`, the six groups in priority order (README §5):
  `video > mobile_screenshot > whatsapp_received > iphone_raw >
  iphone_photo > other`.
- `resolve_routing_group`: given a mapping of routing-group name to the
  `RuleResult` that nominated it (only groups whose rule actually fired are
  present as keys), returns the highest-priority group and its winning
  result — the roadmap's "priority resolver."
- `build_classification_result`: assembles a full `ClassificationResult`
  from a resolved routing group + winning `RuleResult` (or the "no rule
  fired" fallback to `other`), applying a single shared review-confidence
  threshold. This is scaffolding for Phase 9/10 rules to call into, not a
  new detection signal.
- `Classification` SQLModel table (README §24.3), including the
  `automatic_` / `manual_` / `effective_routing_group` split (README §15.3)
  even though nothing populates `manual_routing_group` until Phase 12.
- `ClassificationRepository`, mirroring `MediaMetadataRepository`'s shape.
- Unit tests for `resolve_routing_group` and `build_classification_result`
  against **synthetic** `RuleResult` data (no real rule exists yet) — this
  is the roadmap's stated done criterion.

### Out (later phases)

- Any concrete rule (video/iPhone/RAW — Phase 9; WhatsApp/screenshot —
  Phase 10).
- Country resolution / GPS-derived fields — Phase 11.
- A `classify` CLI command or wiring against real scanned data — Phase 12.
- Manual override recording (`manual_routing_group`, `override_timestamp`)
  — Phase 12; the column exists on the table now (README §24.3 already
  lists it) but nothing writes to it yet.

## Source of truth

- README §15 "Motor de classificação" — `RuleResult`/`ClassificationRule`/
  `ClassificationResult` shapes, verbatim.
- README §5 "Grupos principais de roteamento" — the six routing groups and
  their fixed priority order.
- README §4 "Princípio de classificação multidimensional" — why
  `media_kind`/`source_origin`/`image_format`/`routing_group`/`confidence`
  stay independent fields rather than collapsing into one label.
- README §24.3 "Classification" — the persisted table's column list.
- `specs/roadmap.md` Phase 8 entry and its *Done when* criterion.
- `specs/mission.md` principles 4 (explainable classification), 5
  (multidimensional classification), 6 (deterministic rules first).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/rules/engine.py` | `rules/` is already reserved in `AGENTS.md`'s repository layout for this exact purpose; `engine.py` holds the shared contract, concrete rule modules (Phase 9/10) become siblings. |
| Priority resolution shape | `resolve_routing_group(candidates: Mapping[str, RuleResult]) -> tuple[str, RuleResult \| None]` | A rule "fires" by being present as a key in `candidates` at all — callers (future concrete rules) simply omit a group's key when their rule doesn't apply, rather than the resolver needing its own applicability threshold. Keeps the resolver a pure priority lookup, trivially testable with a synthetic dict. |
| Fallback group | `"other"` with `winner=None` when `candidates` is empty or contains no group ahead of it | Matches README §5.1 — `other` is last in priority and is also the correct behavior when nothing matched. |
| Review threshold | A single shared `DEFAULT_REVIEW_THRESHOLD = 0.60` in `build_classification_result`, overridable per call | README doesn't specify one global cutoff (screenshot's own confidence bands in §13.4 are rule-specific, Phase 10), but the roadmap's `ClassificationResult.requires_review` field must come from *some* policy for this phase's synthetic tests to exercise. A single overridable default keeps Phase 8 unopinionated about rule-specific bands while still being concretely testable; Phase 10's screenshot rule is free to pass its own threshold or set `requires_review` via its own reasons/score design. |
| `Classification.gps_latitude`/`gps_longitude` naming | Plain `float \| None` columns, not literally suffixed `_encrypted_or_hidden` as README §24.3 spells them | The suffix documents a *handling policy* ("don't surface raw coordinates in default output/logs" — README §28 "não registrar coordenadas em logs comuns"), not a literal column transformation; no encryption is implemented. Naming matches `MediaMetadata.gps_latitude/gps_longitude` (Phase 6) for consistency. The redaction-from-output policy itself is enforced where output is generated (Phase 11 country resolution, Phase 13 reports), not at the storage layer. |
| `override_timestamp` | Not added to `Classification` yet | README §15.3 introduces it alongside manual override recording, which is Phase 12's job; adding an always-`None` column now would be dead weight until that phase gives it meaning — unlike `manual_routing_group`/`effective_routing_group`, which README §24.3 already lists as part of the table's baseline shape. |
| Relationship naming | `MediaFile.classification: Optional["Classification"]` / `Classification.media_file: "MediaFile"` | `classification` isn't a reserved SQLAlchemy attribute name (unlike `metadata`, hit in Phase 6 — see `AGENTS.md`), so no rename workaround needed. |

## Constraints

- **Explainable classification** (`specs/mission.md` #4): `RuleResult` and
  `ClassificationResult` both always carry `reasons`; `build_classification_result`
  never produces an empty reasons list (falls back to an explicit
  "no rule matched" reason).
- **Multidimensional classification** (`specs/mission.md` #5): `media_kind`,
  `source_origin`, `image_format`, `routing_group`, `confidence` stay
  independent fields on `ClassificationResult`/`Classification` — no
  collapsing into a single label.
- **Deterministic rules first** (`specs/mission.md` #6): the resolver is a
  pure priority lookup over already-computed scores; no ML/heuristic
  scoring is introduced here.
- SQLModel is the only model layer; `Classification` follows the same
  `Relationship()`/quoted-forward-ref (or `Optional[...]`, per the Phase 6
  gotcha recorded in `AGENTS.md`) convention as `MediaMetadata`.
