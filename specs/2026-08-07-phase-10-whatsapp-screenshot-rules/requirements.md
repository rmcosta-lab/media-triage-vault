# Requirements — Phase 10: WhatsApp + screenshot rules

## Objective

Implement the two probabilistic `ClassificationRule`s that round out the
non-GPS routing groups: `WhatsAppRule` (README §12) and `ScreenshotRule`
(README §13), each unit-tested against README's worked cases — including
the two explicit "this signal alone proves nothing" negatives (§12.4,
§13.3).

## Scope

### In

- `WhatsAppRule` (`routing_group = "whatsapp_received"`): filename regexes
  and directory-name signal (README §12.1) scored per §12.3's table
  (name match `0.65`, directory match `0.45`, absent camera metadata
  `+0.10` — but *only* as a bonus on top of a name/directory signal, never
  alone), capped at `1.00`. A `Sent` directory segment flips the label to
  `whatsapp_sent`; otherwise `whatsapp_received` (§12.2). Absent camera
  metadata alone (§12.4) never classifies.
- `ScreenshotRule` (`routing_group = "mobile_screenshot"`): filename
  regexes (§13.1) score a fixed `0.90` (clears the `>=0.85` auto-classify
  band, §13.4). Failing that, four medium signals (§13.2 — PNG/HEIF
  format, absent camera metadata, vertical orientation, phone-compatible
  aspect ratio; the fifth README signal, "known/near-smartphone
  resolution," is out of scope — see Decisions) are weighted and summed;
  the §13.3 safety rule is enforced explicitly (geometry-only signals
  without a format or metadata-absence anchor never classify, regardless
  of weighted sum) and anything below the `0.60` floor doesn't classify.
- Unit tests reproducing every README §12/§13 worked case, plus a test
  demonstrating the full three-band `requires_review` behavior (§13.4) by
  feeding a `ScreenshotRule` result through Phase 8's
  `build_classification_result` with an explicit `review_threshold=0.85`.

### Out (later phases)

- GPS/country resolution — Phase 11.
- Wiring rules into an orchestrator, `Classification` row, or CLI — Phase
  12 (same boundary as Phase 9).
- OpenCV-based border/text heuristics for screenshots — README §13.2
  explicitly defers this to "uma futura heurística," not the MVP.
- A canonical smartphone-resolution database — no such table is specified
  in the README; see Decisions.

## Source of truth

- README §12 "Regras para identificar arquivos do WhatsApp" (§12.1–§12.4).
- README §13 "Regras para identificar captura de tela de celular"
  (§13.1–§13.4).
- `specs/roadmap.md` Phase 10 entry and its *Done when* criterion.
- `specs/mission.md` principles 4 (explainable classification), 6
  (deterministic rules first).
- Phase 8's `backend/app/rules/engine.py` (`RuleResult`,
  `build_classification_result`) and Phase 9's `backend/app/rules/*.py`
  (established module shape: one file per rule family, `metadata: dict`
  keyed by raw ExifTool tag names, no `file_name`/`extension` used as a
  positive signal where README forbids it).

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| WhatsApp "metadata absent" bonus | Only added on top of an existing name/directory match, never contributes alone | README §12.3's own table row ("Apenas metadados ausentes: não classificar") and §12.4 both say this explicitly — absence of EXIF alone must never indicate WhatsApp. |
| WhatsApp directory match | Any path segment containing the substring `"whatsapp"` (case-insensitive) | Covers every example in §12.1 (`WhatsApp Images`, `WhatsApp/Media`, `Media/WhatsApp Images`, ...) with one check instead of enumerating each literal path. |
| WhatsApp `Sent` direction | Any path segment case-insensitively equal to `"sent"` | §12.2 only describes "uma pasta chamada `Sent`"; exact-segment match (not substring) avoids false positives like a folder literally named `"Sentimental"`. |
| Screenshot medium signals | Four of README §13.2's five: PNG/HEIF format (`0.25`), absent camera metadata (`0.20`), vertical orientation (`0.15`), phone-compatible aspect ratio `0.40–0.75` width/height (`0.15`) | The fifth — "known/near-smartphone resolution" — has no canonical resolution list anywhere in the README/specs; inventing one would be a heuristic beyond what's specified (`specs/mission.md` #6). Aspect ratio is a reasonable, already-specified proxy for "smartphone-shaped." |
| Screenshot safety rule (§13.3) enforcement | Explicit code check: if neither the format nor the metadata-absence signal is present, return `0.0` regardless of the geometry signals' sum | The medium-signal weights already keep geometry-only combinations under the `0.60` floor by construction, but an explicit check makes README §13.3 a direct, self-documenting guarantee rather than an emergent property of tuning that could silently break if weights are ever adjusted. |
| Screenshot confidence bands → `requires_review` | Not encoded in `RuleResult` (README §15's schema is fixed to `label`/`score`/`reasons`); demonstrated instead via `build_classification_result(..., review_threshold=0.85)` in a dedicated test | Matches the precedent Phase 8 already set ("Phase 10's screenshot rule is free to pass its own threshold... via its own score design") — the rule stays a pure `(media, metadata) -> RuleResult` function; band-to-`requires_review` mapping is an assembly-time concern Phase 12's orchestrator owns. |
| Screenshot medium-signal ceiling | Format + absent-metadata + vertical + aspect ratio sums to `0.75` — always below the `0.85` auto band | Medium signals alone should never claim the same certainty as an explicit filename match (§13.1 vs §13.2's own framing as weaker evidence); only a name match reaches `>=0.85`. |

## Constraints

- **Explainable classification** (`specs/mission.md` #4): every `RuleResult`
  carries specific reasons, including the two "not sufficient alone" cases.
- **Deterministic rules first** (`specs/mission.md` #6): fixed regexes and
  a fixed scoring table; no OpenCV/ML heuristics.
- README §12.4 / §13.3: absent metadata alone (WhatsApp) and
  dimensions/orientation alone (screenshot) never classify by themselves.
- Neither rule reads anything beyond `media`/`metadata` fields already
  produced by Phases 4–6 — no new file I/O or external tool calls.
