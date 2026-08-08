# Validation — Phase 14: Destinations + move plan (dry run)

### Functional (US-003 acceptance criteria)

- [x] The user can define a destination folder per `routing_group` —
      `media-organizer destinations --scan-id --config <file.json>`
      creates one `DestinationRule` per mapped group — verified by
      `test_set_destination_rules_creates_one_rule_per_group` and a
      manual run against `backend/tests/fixtures/` (6 groups mapped).
- [x] The plan validates permissions — `DESTINATION_NOT_WRITABLE` check
      implemented in `generate_move_plan` (`_nearest_existing_ancestor_writable`).
- [x] The plan validates disk space — `INSUFFICIENT_DISK_SPACE` check per
      destination volume — `test_insufficient_disk_space_is_blocked`.
- [x] The plan detects conflicts — `NAME_COLLISION` (including a
      case-only collision) and `DUPLICATE_IN_PLAN` —
      `test_case_only_collision_is_blocked`,
      `test_duplicate_in_plan_is_blocked_on_second_file`.
- [x] The plan presents source and destination per file — every
      `MoveOperation` row carries `source_path` and
      `planned_destination_path` — asserted in the integration test and
      visible in the manual `plan` run output.
- [x] Every planned destination includes the sanitized routing group between
      the configured root and the optional country subfolder — asserted by
      `test_happy_path_one_file_one_mapped_group`, the country-subfolder tests,
      and the CLI/API integration tests.
- [x] The plan computes total volume — `MovePlanSummary.total_bytes_planned`
      (manual run: `total_bytes_planned=7012`).
- [x] A dry run is generated — `MovePlan`/`MoveOperation` rows persisted —
      `test_destinations_and_plan_cli_end_to_end`.
- [x] Nothing is executed automatically — no file under the source root
      or the destination root is created, moved, renamed, or deleted by
      `destinations` or `plan` — verified in tests and manually (see
      Safety section).

### Roadmap done criterion

- [x] A case-only collision (`Foto.jpg` vs. an already-present `foto.jpg`)
      is reported as a plan error (`NAME_COLLISION`), not raised as an
      exception or silently skipped —
      `test_case_only_collision_is_blocked`.
- [x] An over-length destination path (> 260 characters) is reported as a
      plan error (`PATH_TOO_LONG`) at plan time, not deferred —
      `test_over_length_path_is_blocked`.
- [x] A complete plan is produced end to end from an existing scan +
      classification through the CLI — manual `scan` → `classify` →
      `destinations` → `plan` run against `backend/tests/fixtures/`:
      8 files planned, 0 blocked, 1 correctly excluded as
      `skipped_unclassified` (the `.mp4`-renamed-`.tmp` access-error
      fixture that never got a `Classification` row).

### Tests

- [x] `sanitize_path_component` covered for forbidden characters,
      trailing dot/space, and every reserved Windows device name —
      `test_destination_paths.py` (parametrized over `CON`/`PRN`/`AUX`/
      `NUL`/`COM1`/`COM9`/`LPT1`/`LPT9`/`CON.txt`).
- [x] `exceeds_windows_path_limit` covered at the 260-character boundary.
- [x] `paths_collide` covered for a case-only pair and an NFC/NFD pair of
      the same name.
- [x] Every §16 Etapa 5 validation has at least one unit test: source
      missing, source changed since scan, source locked (monkeypatched),
      source equals destination, path too long, duplicate in plan, name
      collision, insufficient disk space (monkeypatched); destination-
      not-writable is exercised indirectly by every other passing test
      (the check runs and returns `True` for a normal temp directory) —
      `test_move_plan_service.py`, 14 tests.
- [x] Country-subfolder path construction tested both enabled and
      disabled, always after the routing-group segment —
      `test_country_subfolder_enabled_adds_segment`,
      `test_country_subfolder_disabled_is_flat`.
- [x] Files with an unmapped group and files with no `Classification` row
      are excluded from the plan and counted correctly —
      `test_unmapped_group_excluded_from_plan`,
      `test_unclassified_file_excluded_from_plan`.
- [x] `set_destination_rules` rejects an unknown routing-group key and
      replaces (not duplicates) an existing mapping on a second call —
      `test_set_destination_rules_rejects_unknown_routing_group`,
      `test_set_destination_rules_replaces_not_duplicates` (this test
      caught a real bug: `DestinationRuleRepository.replace_for_scan` now
      flushes the deletes before adding replacement rows, since
      SQLAlchemy's default flush order runs inserts before deletes and
      was tripping the `(scan_id, routing_group)` unique constraint).
- [x] Integration test runs `scan` → `classify` → `destinations` → `plan`
      over `backend/tests/fixtures/` and asserts the persisted plan
      matches expectations — `test_destinations_and_plan_cli_end_to_end`.
- [x] Fixtures are byte-identical before/after every test in this phase
      (SHA-256 comparison) — same pattern as every prior integration
      test; confirmed additionally via `git status` after the manual run.

### Safety

- [x] No network call is made — `destinations.py`/`move_plan.py`/
      `destination_paths.py` only call stdlib (`os`, `shutil`, `pathlib`,
      `json`), SQLModel, and already-audited repository code — confirmed
      by reading every new module's imports.
- [x] No source file is modified, moved, renamed, or deleted by any code
      in this phase — SHA-256 comparison in the integration test, plus a
      `git status --short backend/tests/fixtures/` check after the
      manual run (clean).
- [x] No destination directory or file is created during plan generation
      — asserted in `test_generate_move_plan_never_writes_to_destination`
      and confirmed manually: after the full `scan`→`classify`→
      `destinations`→`plan` run, the configured destination root did not
      exist on disk at all.
- [x] `collision_policy` values other than `"error"` are rejected —
      `generate_move_plan` raises `ValueError` up front,
      `test_plan_cli_rejects_unsupported_collision_policy`; `"overwrite"`
      is not implemented anywhere in this phase's code (confirmed by
      reading `move_plan.py` — `SUPPORTED_COLLISION_POLICY = "error"` is
      the only accepted value).

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean (verified via `ruff format .`
      reporting "0 files reformatted" on the final run).
- [x] `uv run mypy backend` clean — "Success: no issues found in 79
      source files".
- [x] `uv run pytest` green — 224 passed (39 new: 19 path-helper unit,
      3 destinations-service unit, 14 move-plan-service unit,
      3 plan-CLI integration).
- [x] `uv run media-organizer destinations --help` and
      `uv run media-organizer plan --help` run without error — verified
      manually.
