# Plan — Phase 10: WhatsApp + screenshot rules

## 1. WhatsApp rule

- New `backend/app/rules/whatsapp.py`:
  - `NAME_PATTERNS`: the four README §12.1 regexes, case-insensitive.
  - `NAME_MATCH_SCORE = 0.65`, `DIRECTORY_MATCH_SCORE = 0.45`,
    `METADATA_ABSENT_SCORE = 0.10`, `MAX_SCORE = 1.00`.
  - `_directory_segments(relative_path: str) -> list[str]` — splits on
    both `/` and `\`, drops the filename.
  - `_name_matches`, `_directory_has_whatsapp` (substring `"whatsapp"`,
    case-insensitive, any segment), `_directory_has_sent` (segment
    case-insensitively `== "sent"`), `_camera_metadata_absent`
    (`not metadata.get("Make")`).
  - `class WhatsAppRule:` — `name = "whatsapp"`,
    `routing_group = "whatsapp_received"`. `evaluate`: no name/directory
    signal at all → `0.0` (distinct reason text for "metadata absent
    alone" vs "no signal"); otherwise sum name + directory + (metadata
    bonus only if name or directory matched), cap at `MAX_SCORE`, label
    `whatsapp_sent`/`whatsapp_received` from the `Sent` check.

## 2. Screenshot rule

- New `backend/app/rules/screenshot.py`:
  - `NAME_PATTERNS`: the four README §13.1 regexes, case-insensitive.
  - `STRONG_NAME_SCORE = 0.90`, `AUTO_CLASSIFY_THRESHOLD = 0.85` (exported
    for the assembly-time test, not used internally),
    `REVIEW_THRESHOLD = 0.60` (the classify-at-all floor).
  - Medium-signal weights and helpers: `_is_png_or_heif`,
    `_camera_metadata_absent`, `_is_vertical`, `_has_phone_aspect_ratio`
    (`0.40 <= width/height <= 0.75` when `height > width`).
  - `class ScreenshotRule:` — `name = "screenshot"`,
    `routing_group = "mobile_screenshot"`. `evaluate`: name match short-
    circuits to `STRONG_NAME_SCORE`; else compute the four medium signals,
    explicitly return `0.0` if neither format nor metadata-absence fired
    (§13.3 safety rule), else sum weights and return `0.0` if under
    `REVIEW_THRESHOLD`, else the summed score.

## 3. Tests

- `backend/tests/unit/test_whatsapp_rule.py`:
  - Each §12.1 name pattern individually → `score=0.65` (+ direction).
  - Directory-only match (no name pattern) → `score=0.45`.
  - Name + directory + absent metadata → `score=1.00` (capped, not `1.20`).
  - `Sent` directory segment → `label="whatsapp_sent"`.
  - No `Sent` segment, sufficient signal → `label="whatsapp_received"`.
  - README §12.4: absent metadata alone, no name/directory match →
    `score=0.0`.
  - No signals at all → `score=0.0`.
- `backend/tests/unit/test_screenshot_rule.py`:
  - Each §13.1 name pattern → `score=0.90`.
  - README §13.3 safety rule: vertical + phone aspect ratio only (no
    format, no metadata-absence) → `score=0.0`, even though the raw
    geometry weights would otherwise sum above `0`.
  - Format + metadata-absent + vertical + aspect (all four) → `score=0.75`
    (review band, below `0.85`).
  - Format + metadata-absent only → below `REVIEW_THRESHOLD` → `score=0.0`
    (documents that two signals isn't automatically enough either — only
    exercised as a boundary case, not a spec requirement beyond §13.3).
  - Format + metadata-absent + vertical (three signals, boundary) →
    `score=0.60`, exactly at the classify floor.
  - A `build_classification_result` test: three synthetic candidate
    scores (`0.90`, `0.75`, and — via manual `RuleResult` construction,
    since the rule itself never returns a sub-`0.60` non-zero score —
    a hypothetical `0.65`) run through
    `build_classification_result(..., review_threshold=AUTO_CLASSIFY_THRESHOLD)`
    and assert `requires_review` is `False`/`True`/`True` respectively,
    demonstrating README §13.4's three bands end to end.

## 4. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
