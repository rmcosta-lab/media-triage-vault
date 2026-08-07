# Plan — Phase 9: Video + iPhone + RAW rules

## 1. Video rule

- New `backend/app/rules/video.py`:
  - `class VideoRule:` — `name = "video"`, `routing_group = "video"`.
  - `evaluate(self, media: MediaFile, metadata: dict[str, Any]) -> RuleResult`:
    collects reasons from `media.mime_type`/`metadata.get("MIMEType")`
    starting with `"video/"`, `media.file_type`/`metadata.get("FileType")`
    matching a small known-video `FileType` set (`MP4`, `MOV`, `M4V`,
    `3GP`, `AVI`, `MKV`, `WEBM`), and `media.media_kind == "video"`. Score
    `1.0` if any signal present, else `0.0` with an explicit "no video
    signal" reason.

## 2. iPhone rule + iPhone RAW rule

- New `backend/app/rules/iphone.py`:
  - Constants: `HIGH_CONFIDENCE = 0.98`, `INSUFFICIENT_SIGNAL_SCORE = 0.0`,
    secondary-signal ladder `_SECONDARY_SIGNAL_SCORES = {1: 0.55, 2: 0.70, 3: 0.85}`
    (capped at the 3-signal value for 3+).
  - `_is_apple_make_and_iphone_model(metadata: dict[str, Any]) -> bool`:
    `metadata.get("Make") == "Apple"` and
    `str(metadata.get("Model", "")).startswith("iPhone")`.
  - `_iso6709_pattern` (compiled regex) and
    `_count_secondary_signals(metadata: dict[str, Any]) -> tuple[int, list[str]]`:
    checks `Software`, `Encoder`/`CompressorName`, `HandlerDescription`,
    `LocationInformation`, returns the count and the matched reason
    strings.
  - `class IPhoneRule:` — `name = "iphone"`, `routing_group = "iphone_photo"`.
    `evaluate`: high-confidence branch first (README §10.1); else count
    secondary signals (README §10.2) and score via the ladder, `0.0`/
    `"unknown"` label when none found (README §10.3 — filename is never
    consulted).
  - `class IPhoneRawRule:` — `name = "iphone_raw"`, `routing_group = "iphone_raw"`.
    `evaluate`: `_is_dng(media, metadata)` (FileType `"DNG"` or `.dng`
    extension) AND `_is_apple_make_and_iphone_model` → high confidence
    (reuse `HIGH_CONFIDENCE`); DNG without the Apple/iPhone signal → `0.0`,
    reason noting README §11's "routes to other"; not a DNG at all → `0.0`.

## 3. Tests

- `backend/tests/unit/test_video_rule.py`: MIME-only match, `FileType`-only
  match, `media_kind="video"`-only match (mirrors a Phase 6-validated row),
  corrupted video (`error_code="VIDEO_UNREADABLE"`, `media_kind="video"`)
  still fires, no-signal image scores `0.0`.
- `backend/tests/unit/test_iphone_rule.py`:
  - README §10.1 worked example (`Make=Apple`, `Model=iPhone 15 Pro Max`)
    → `score=0.98`, `label="iphone_camera"`, reasons mention both fields.
  - README §10.2 video cases: 1, 2, and 3+ secondary signals present
    without direct Make/Model → ladder scores.
  - README §10.3: `file_name="IMG_1234.JPG"`/`"IMG_1234.MOV"`, empty
    metadata → `score <= 0.40` (asserts the literal cap, even though the
    implementation returns `0.0`).
  - README §10.4: Make/Model absent (stripped by export) and no secondary
    signals either → `score == 0.0`, `label="unknown"`.
- `backend/tests/unit/test_iphone_raw_rule.py`:
  - README §11 worked case: `media_kind="image"`, `FileType="DNG"`,
    `Make=Apple`, `Model` starts with iPhone → high confidence,
    `routing_group="iphone_raw"`.
  - `.dng` extension without `FileType` set also matches.
  - Non-Apple DNG (`Make="Canon"` or absent) → `score=0.0`.
  - Non-DNG image with Apple Make/Model → `score=0.0` (this rule only
    claims DNG files; `IPhoneRule` owns the non-RAW case).
  - A synthetic end-to-end check: feed both `IPhoneRawRule` (non-Apple DNG,
    score `0.0`) and no other candidate into
    `backend.app.rules.engine.resolve_routing_group` and assert the result
    is `("other", None)` — demonstrates the "non-Apple DNG routes to
    other" roadmap wording as resolver behavior, not just an isolated
    rule-score assertion.

## 4. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
