# Requirements — Phase 12: Classify CLI + overrides

## Objective

Wire Phases 8–11 (rule engine core, video/iPhone/RAW rules, WhatsApp/
screenshot rules, offline country resolution) into one orchestrator and a
`media-organizer classify` command, so US-002 (README §38) passes end to
end: an existing scan's files get classified with confidence and reasons,
persisted to `Classification`, and a manual override can flip a file's
effective routing group via the CLI — without ever moving a file.

## Scope

### In

- `classify_scan(session, scan_id) -> ClassificationSummary`
  (`backend/app/services/classification.py`): for every `image`/`video`
  `MediaFile` row of a scan, runs all five Phase 9/10 rules
  (`VideoRule`, `IPhoneRule`, `IPhoneRawRule`, `WhatsAppRule`,
  `ScreenshotRule`) against the row's `MediaMetadata.raw_json` (the same
  raw ExifTool tag dict the rules were unit-tested against), resolves the
  winning routing group via Phase 8's `resolve_routing_group`, determines
  `image_format` (README §6.2's RAW extension list vs. everything else),
  resolves GPS → country via Phase 11's `CountryResolver`, and persists
  one `Classification` row per file.
- Re-running `classify_scan` on an already-classified scan **updates**
  the automatic fields (`automatic_routing_group`, `confidence`,
  `reasons_json`, `source_origin`, GPS/country fields) without touching an
  existing `manual_routing_group`/`effective_routing_group` — a manual
  override survives re-classification.
- Screenshot's own confidence bands (README §13.4) are honored at
  assembly time: `review_threshold=0.85` when the winning candidate is
  `mobile_screenshot`, the shared `DEFAULT_REVIEW_THRESHOLD=0.60`
  otherwise.
- `media-organizer classify --scan-id <id>`: runs `classify_scan`, prints
  one line per file with its `effective_routing_group`, `confidence`, and
  `reasons` (README §38 "mostra confiança"/"mostra justificativa"), then a
  summary.
- `media-organizer override <media_file_id> <routing_group>`: validates
  `routing_group` against Phase 8's `ROUTING_GROUPS`, requires an existing
  `Classification` row (i.e. `classify` already ran), sets
  `manual_routing_group`/`effective_routing_group` to the given value and
  stamps `override_timestamp` (README §15.3) — a new `Classification`
  column, deferred from Phase 8 to exactly this phase.
- Unit + integration tests covering US-002's acceptance list (README
  §38): video/screenshot/WhatsApp/iPhone/iPhone-RAW classification,
  country by GPS, confidence + reasons shown, no file ever moved, plus
  the override round-trip and its survival across re-classification.

### Out (later phases)

- FastAPI/HTTP surface for classify/override — Phase 17+.
- Thumbnails/HTML/CSV reports — Phase 13.
- Destination mapping / move planning — Phase 14+.

## Source of truth

- README §38 "Segunda história de usuário — US-002" — the acceptance list
  this phase must satisfy end to end.
- README §15.3 "Correção manual" — `automatic_`/`manual_`/
  `effective_routing_group`/`override_timestamp`.
- README §24.3 "Classification" — the persisted table's column list
  (already built in Phase 8; this phase is the first to populate it).
- `specs/roadmap.md` Phase 12 entry and its *Done when* criterion.
- `specs/mission.md` principles 2 (read-only until Phase 14), 4
  (explainable classification).
- Phase 8's `rules/engine.py`, Phase 9's `rules/video.py`/`rules/iphone.py`,
  Phase 10's `rules/whatsapp.py`/`rules/screenshot.py`, Phase 11's
  `services/country.py` — this phase only orchestrates them; no new
  detection/scoring logic is added here.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Module location | `backend/app/services/classification.py` | Fourth occupant of `services/`, same orchestration shape as `scanner.py`/`metadata.py` (Phases 4/6): reads rows an earlier phase wrote, runs a batch operation, persists results. |
| `metadata` dict source | `json.loads(media_metadata.raw_json)` when a `MediaMetadata` row exists, else `{}` | Exactly the dict shape every Phase 9/10 rule was unit-tested against (`MediaMetadata.raw_json` already *is* the README §8.2 ExifTool tag subset — Phase 6). No second normalization layer. |
| Candidate assembly | `{rule.routing_group: result for rule in RULES if (result := rule.evaluate(media, metadata)).score > 0}` | Matches Phase 8's resolver contract exactly: a rule "fires" by being a key in the candidates mapping. Each of the five rules has a distinct fixed `routing_group` attribute, so no collision is possible. |
| Screenshot review threshold | `review_threshold=ScreenshotRule.AUTO_CLASSIFY_THRESHOLD` (`0.85`) when the winner is `mobile_screenshot`; `DEFAULT_REVIEW_THRESHOLD` (`0.60`) otherwise | This is exactly the assembly-time policy Phase 8's own decision doc anticipated ("Phase 10's screenshot rule is free to pass its own threshold... via its own score design") — Phase 12 is where an orchestrator finally exists to apply it. |
| `image_format` | `"not_applicable"` for `media_kind="video"`; `"raw"` when the extension is in README §6.2's RAW list or `MediaFile.file_type == "DNG"`; `"standard"` otherwise | README §6.2/§11 distinguish RAW images from standard images; videos have no meaningful image format. |
| Re-classification + manual override | `classify_scan` always overwrites the *automatic* fields; `effective_routing_group` is only overwritten when `manual_routing_group` is `None` | A manual correction (README §15.3) must survive a re-run of `classify` after, say, a metadata fix — otherwise the override CLI would be useless the moment anyone re-scans. |
| Override validation | `routing_group` must be one of Phase 8's `ROUTING_GROUPS`; the target `Classification` row must already exist | An override edits an existing automatic result (README §15.3's framing — "a interface deverá permitir **alterar** o grupo") rather than creating one from nothing; requiring `classify` to have run first keeps the CLI's error message actionable. |
| CLI output | One line per file: `relative_path -> effective_routing_group (confidence=X.XX, requires_review=Y) reasons: [...]` | Directly satisfies README §38's "mostra confiança"/"mostra justificativa" as something the CLI itself surfaces, not just a silent DB write. |

## Constraints

- **Read-only until Phase 14** (`specs/mission.md` #2): classification only
  reads `MediaFile`/`MediaMetadata` and writes `Classification` rows and
  CLI stdout — never touches a file under the scanned root.
- **Explainable classification** (`specs/mission.md` #4): every persisted
  `Classification` row carries `confidence`, `requires_review`, and a
  non-empty `reasons_json`.
- No network call; `CountryResolver`/rules are the same audited Phase
  9-11 code, unmodified in this phase beyond the review-threshold wiring
  described above.
