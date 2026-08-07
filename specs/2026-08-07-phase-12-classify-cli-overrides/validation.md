# Validation — Phase 12: Classify CLI + overrides

### Functional (US-002, README §38)

- [x] Classifies video — `test_classify_scan_routes_fixtures_correctly`
      (`sample_video.mp4`, `misnamed_video_as_jpg.jpg`, `corrupt_video.mp4`
      all → `video`).
- [x] Classifies screenshot — same test (`Screenshot_20260730-152000.png`
      → `mobile_screenshot`).
- [x] Classifies WhatsApp — verified manually
      (`IMG-20260730-WA0001.jpg` → `whatsapp_received`, confidence 0.75).
- [x] Identifies iPhone — same test/manual run
      (`iphone_jpeg_gps.jpg`/`iphone_heic.heic` → `iphone_photo`,
      confidence 0.98).
- [x] Separates iPhone RAW — covered by `IPhoneRawRule` (Phase 9),
      exercised through `_build_candidates`/`_classify_one` in this
      phase's unit tests; no RAW fixture exists yet so this is orchestration
      wiring, not a new behavior — `test_determine_image_format_dng_*`.
- [x] Identifies country by GPS —
      `iphone_jpeg_gps.jpg` → `country_code="JP"`, verified in
      `test_classify_scan_routes_fixtures_correctly` and manually
      (`country_name="Japan"`).
- [x] Shows confidence — CLI prints `confidence=X.XX` per file;
      `test_classify_and_override_cli_end_to_end` asserts the token is
      present in stdout.
- [x] Shows justification (reasons) — CLI prints `reasons: [...]` per
      file; verified manually against real fixture output.
- [x] Does not move files — SHA-256 comparison in
      `test_classify_and_override_cli_end_to_end`; manually verified with
      `md5sum` against the real `backend/tests/fixtures/` files.
- [x] A manual override changes `effective_routing_group` and survives a
      re-run of `classify` —
      `test_classify_scan_rerun_does_not_duplicate_or_clobber_override`,
      `test_classify_and_override_cli_end_to_end`; manually verified too.

### Tests

- [x] Unit tests cover `_determine_image_format`, `_build_candidates`, and
      the screenshot-specific review threshold at assembly time — see
      `test_classification_service.py`.
- [x] Integration test runs the full scan → detect → extract → classify
      pipeline over fixtures and asserts per-file routing groups and the
      Tokyo → `JP` country resolution —
      `test_classify_scan_routes_fixtures_correctly`.
- [x] Integration test confirms re-running `classify_scan` doesn't
      duplicate rows and doesn't clobber a manual override —
      `test_classify_scan_rerun_does_not_duplicate_or_clobber_override`.
- [x] Integration test exercises `classify` and `override` through the
      real Typer `app` (`CliRunner`), including the invalid-routing-group
      and no-classification-yet error paths —
      `test_classify_and_override_cli_end_to_end`,
      `test_override_invalid_routing_group_exits_nonzero`,
      `test_override_before_classify_exits_nonzero`.
- [x] Fixtures are byte-identical before/after every CLI run in this
      phase's tests.

### Safety

- [x] No network call is made — `classification.py`/`cli/main.py`'s new
      commands only call already-audited Phase 8-11 code plus stdlib
      `json`/`datetime`.
- [x] No source file under a scanned root is modified, moved, or deleted
      — confirmed by SHA-256 comparison (automated) and `md5sum`
      (manual).
- [x] No external tool invocation beyond what Phases 4-6 already perform
      upstream of this phase — confirmed by reading `classification.py`
      (no `run_tool`/`subprocess` import).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "62 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 62 source
      files" (formalized `routing_group: str` onto the `ClassificationRule`
      Protocol in `rules/engine.py`, since the orchestrator needed it
      structurally — updated Phase 8's synthetic protocol-conformance test
      accordingly).
- [x] `uv run pytest` green — 167 passed (16 new: 11 unit, 5 integration).
- [x] `uv run media-organizer classify --help` and
      `uv run media-organizer override --help` run without error —
      verified manually alongside a full real-fixture `scan` → `classify`
      → `override` run.
