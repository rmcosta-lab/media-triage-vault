# Plan — Phase 12: Classify CLI + overrides

## 1. Model

- `backend/app/models/classification.py`: add
  `override_timestamp: datetime | None = None` (README §15.3, deferred
  from Phase 8).

## 2. Classification orchestrator

- New `backend/app/services/classification.py`:
  - `RAW_EXTENSIONS = frozenset({".dng", ".cr2", ".cr3", ".nef", ".arw", ".raf", ".rw2", ".orf"})`
    (README §6.2).
  - `RULES: tuple[ClassificationRule, ...]` — instances of `VideoRule`,
    `IPhoneRule`, `IPhoneRawRule`, `WhatsAppRule`, `ScreenshotRule`.
  - `ClassificationSummary` frozen dataclass: counts per routing group,
    `requires_review`, `skipped` (unsupported/no `media_kind`).
  - `_load_metadata_dict(media_metadata: MediaMetadata | None) -> dict[str, Any]` —
    `json.loads(media_metadata.raw_json)` or `{}`.
  - `_determine_image_format(media: MediaFile) -> str`.
  - `_build_candidates(media: MediaFile, metadata: dict[str, Any]) -> dict[str, RuleResult]`.
  - `_review_threshold_for(routing_group: str) -> float` — the screenshot
    special case from `requirements.md`.
  - `_classify_one(media: MediaFile, metadata: dict[str, Any]) -> ClassificationResult`:
    candidates → `build_classification_result` with the right threshold.
  - `classify_scan(session, scan_id, *, on_progress=None) -> ClassificationSummary`:
    iterate `MediaFileRepository.list_by_scan(scan_id)` filtered to
    `media_kind in ("image", "video")`; for each, load its
    `MediaMetadata`, classify, resolve GPS/country
    (`extract_coordinates` + `get_default_resolver().resolve`), and
    upsert a `Classification` row via `ClassificationRepository` —
    create if none exists for the `media_file_id`, else update in place
    (preserving `manual_routing_group`/`effective_routing_group`/
    `override_timestamp` when a manual override is already set).

## 3. CLI

- `backend/app/cli/main.py`:
  - `@app.command("classify")` — `classify_command(scan_id: int = typer.Option(..., "--scan-id"), database: Path | None = typer.Option(None, "--database", hidden=True))`:
    opens the session, calls `classify_scan` with an `on_progress` that
    echoes one line per classified file (path, effective routing group,
    confidence, `requires_review`, reasons), then a final summary line.
  - `@app.command("override")` — `override_command(media_file_id: int = typer.Argument(...), routing_group: str = typer.Argument(...), database: Path | None = typer.Option(None, "--database", hidden=True))`:
    validates `routing_group` against `ROUTING_GROUPS` (exits `1` with a
    clear message if invalid), loads the `Classification` row for
    `media_file_id` (exits `1` if none — "run classify first"), sets
    `manual_routing_group`/`effective_routing_group`/`override_timestamp`,
    persists, echoes confirmation.

## 4. Tests

- `backend/tests/unit/test_classification_service.py`:
  - `_determine_image_format` — video → `not_applicable`; `.dng` → `raw`;
    `.jpg` → `standard`.
  - `_build_candidates` — synthetic `MediaFile`/metadata combos exercising
    each rule's routing group, and a case where no rule fires (empty
    candidates).
  - `_classify_one` — the screenshot-threshold special case: a
    `mobile_screenshot` result at `0.75` has `requires_review=True`,
    while the same score for a different routing group (mocked candidate)
    would not be forced through the `0.85` gate.
- `backend/tests/integration/test_classify_cli.py`:
  - Full pipeline: scan → detect → extract metadata → `classify_scan`
    over the fixtures directory (temp copy + temp database, same pattern
    as `test_metadata_extraction.py`/`test_scan_cli.py`). Assert:
    `sample_video.mp4` → `video`; `iphone_jpeg_gps.jpg` → `iphone_photo`,
    `country_code="JP"`; `IMG-20260730-WA0001.jpg` → some WhatsApp/other
    result consistent with the rule's own scoring (fixture has no
    WhatsApp name pattern, so exercises the "insufficient signal" path
    honestly rather than asserting a false positive);
    `Screenshot_20260730-152000.png` → `mobile_screenshot`.
  - Re-running `classify_scan` a second time doesn't duplicate
    `Classification` rows (one per `media_file_id`) and doesn't reset an
    existing manual override.
  - CLI `classify --scan-id` (via `CliRunner`) exits `0` and its stdout
    contains at least one routing group name and a `confidence=` token.
  - CLI `override <id> <group>` sets `effective_routing_group` and
    `override_timestamp`, verified by reading the `Classification` row
    back; an invalid routing group exits non-zero; overriding a
    non-classified file exits non-zero.
  - No fixture file is modified (hash comparison), matching every prior
    CLI test.

## 5. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer classify --help` and
  `uv run media-organizer override --help` run cleanly.
