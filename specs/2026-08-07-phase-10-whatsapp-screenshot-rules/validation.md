# Validation — Phase 10: WhatsApp + screenshot rules

### Functional

- [x] README §12–13 cases pass as unit tests (roadmap done criterion),
      including the "absent EXIF alone proves nothing" negatives (§12.4)
      and the screenshot safety-rule negative (§13.3) —
      `test_readme_12_4_absent_metadata_alone_does_not_classify`,
      `test_readme_13_3_safety_rule_geometry_only_does_not_classify`.
- [x] WhatsApp scoring matches §12.3's table exactly, capped at `1.00` —
      `test_readme_12_1_name_patterns_score_065`,
      `test_directory_only_match_scores_045`,
      `test_name_and_directory_and_absent_metadata_caps_at_100`.
- [x] `Sent` directory segment flips the label to `whatsapp_sent`; absence
      defaults to `whatsapp_received` —
      `test_sent_directory_segment_sets_whatsapp_sent_label`,
      `test_no_sent_directory_defaults_to_whatsapp_received`.
- [x] Screenshot name patterns clear the `>=0.85` auto-classify band;
      medium-signal combinations land in the `0.60–0.84` review band or
      below the `0.60` floor per §13.4 —
      `test_readme_13_1_name_patterns_score_090`,
      `test_all_four_medium_signals_land_in_review_band`,
      `test_three_signals_at_exact_classification_floor`,
      `test_two_signals_below_floor_does_not_classify`.
- [x] `requires_review` three-band behavior is demonstrated end to end via
      `build_classification_result` —
      `test_confidence_bands_drive_requires_review_end_to_end`.

### Tests

- [x] Unit tests cover every README §12.1 filename pattern and the
      directory-only path.
- [x] Unit test covers the WhatsApp score cap at `1.00`.
- [x] Unit test covers §12.4 (metadata absent alone → `0.0`).
- [x] Unit tests cover every README §13.1 filename pattern.
- [x] Unit test covers §13.3 (geometry-only signals → `0.0` regardless of
      weighted sum).
- [x] Unit tests cover the medium-signal review band and the sub-floor
      case.

### Safety

- [x] No network call is made — both modules are pure Python, no I/O
      imports.
- [x] No file I/O, no external tool invocation — confirmed by reading
      `whatsapp.py`/`screenshot.py` (no `backend.app.core.tools` import).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "57 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 57 source files".
- [x] `uv run pytest` green — 136 passed (19 new).
