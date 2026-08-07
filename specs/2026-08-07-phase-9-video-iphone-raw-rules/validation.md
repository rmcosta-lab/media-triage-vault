# Validation — Phase 9: Video + iPhone + RAW rules

### Functional

- [x] README §9–11 cases pass as unit tests (roadmap done criterion) —
      `test_video_rule.py` (5 tests), `test_iphone_rule.py` (7 tests),
      `test_iphone_raw_rule.py` (6 tests), all passing.
- [x] Video rule fires on MIME, `FileType`, or `media_kind="video"` signals
      independently, and on a corrupted (`VIDEO_UNREADABLE`) video —
      `test_video_rule_fires_on_mime_type_alone`,
      `test_video_rule_fires_on_exiftool_file_type_alone`,
      `test_video_rule_fires_on_media_kind_alone`,
      `test_video_rule_fires_for_corrupted_but_still_video_file`.
- [x] iPhone rule reproduces README §15's own worked example exactly
      (`score=0.98`, `label="iphone_camera"`) —
      `test_readme_10_1_high_confidence_worked_example`.
- [x] iPhone rule never scores above `0.40` from filename alone (README
      §10.3) — `test_readme_10_3_filename_alone_is_capped_at_040`.
- [x] iPhone RAW rule fires only for DNG + Apple/iPhone; non-Apple DNG
      scores `0.0` and — combined with the Phase 8 resolver — falls
      through to `other` —
      `test_readme_11_non_apple_dng_does_not_nominate_iphone_raw`,
      `test_non_apple_dng_falls_through_to_other_via_resolver`.

### Tests

- [x] Unit tests cover every README §9 OR-branch (MIME/FileType/media_kind)
      independently — see `test_video_rule.py`.
- [x] Unit tests cover README §10.1 (high confidence), §10.2 (secondary
      QuickTime-adjacent signals, tiered 1/2/3+), §10.3 (filename-alone
      cap), §10.4 (stripped Make/Model, no fallback to filename/visual
      match) — see `test_iphone_rule.py`.
- [x] Unit tests cover README §11 (DNG + Apple/iPhone → `iphone_raw`;
      non-Apple DNG → doesn't nominate; non-DNG → doesn't nominate) — see
      `test_iphone_raw_rule.py`.
- [x] A resolver-level test demonstrates non-Apple DNG's absence of a
      candidate results in `("other", None)` —
      `test_non_apple_dng_falls_through_to_other_via_resolver`.

### Safety

- [x] No network call is made — all three rule modules are pure Python,
      no I/O imports.
- [x] No file I/O, no external tool invocation — rules only read fields
      already on `MediaFile`/a passed-in `dict`; confirmed by reading
      `video.py`/`iphone.py` (no `backend.app.core.tools` import).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "53 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 53 source files".
- [x] `uv run pytest` green — 117 passed (18 new).
