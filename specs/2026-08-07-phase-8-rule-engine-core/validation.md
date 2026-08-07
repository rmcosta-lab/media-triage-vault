# Validation — Phase 8: Rule engine core

### Functional

- [x] Priority resolution is unit-tested with synthetic rule outputs
      (roadmap done criterion): a lower-priority group with a higher score
      still loses to a higher-priority group present in the candidates —
      `test_resolve_routing_group_higher_priority_wins_despite_lower_score`.
- [x] `resolve_routing_group` falls back to `("other", None)` when no
      candidate is applicable — `test_resolve_routing_group_empty_falls_back_to_other`.
- [x] `build_classification_result` produces a fully-populated
      `ClassificationResult` from synthetic `RuleResult` candidates, with
      `requires_review` correctly derived from the confidence threshold —
      `test_build_classification_result_winner_above_threshold_no_review`,
      `test_build_classification_result_winner_below_threshold_requires_review`,
      `test_build_classification_result_custom_review_threshold`.
- [x] `Classification` round-trips through SQLite with its `MediaFile`
      foreign key — `test_classification_round_trips_through_sqlite`.

### Tests

- [x] Unit tests cover `resolve_routing_group`: single candidate, priority
      ordering across multiple candidates, empty mapping, `other` present
      alongside a higher-priority group, `other` alone —
      `test_resolve_routing_group_single_candidate`,
      `test_resolve_routing_group_higher_priority_wins_despite_lower_score`,
      `test_resolve_routing_group_empty_falls_back_to_other`,
      `test_resolve_routing_group_other_loses_to_higher_priority_candidate`,
      `test_resolve_routing_group_other_wins_when_alone`.
- [x] Unit tests cover `build_classification_result`: winner path,
      no-winner fallback path, custom `review_threshold` — see above plus
      `test_build_classification_result_no_winner_falls_back_to_other`.
- [x] A synthetic `ClassificationRule` implementation is exercised against
      the protocol — `test_synthetic_rule_conforms_to_classification_rule_protocol`.

### Safety

- [x] No network call is made — `rules/engine.py` is pure dataclasses/
      Protocol, no I/O.
- [x] No source file under a scanned root is touched — no file I/O in this
      phase beyond SQLite persistence (`Classification` table).
- [x] No external tool (ExifTool/FFprobe) is invoked — confirmed by reading
      `rules/engine.py` (no `backend.app.core.tools` import).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "48 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 48 source files".
- [x] `uv run pytest` green — 99 passed (11 new: 10 rule-engine unit tests
      in `test_rule_engine.py`, 1 model round-trip test in
      `test_classification_model.py`).
