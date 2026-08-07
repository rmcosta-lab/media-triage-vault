# Plan — Phase 14: Destinations + move plan (dry run)

## 1. Path helpers (core)

- New `backend/app/core/destination_paths.py`:
  - `FORBIDDEN_CHARS = '<>:"/\\|?*'` (plus ASCII control chars 0–31).
  - `RESERVED_WINDOWS_NAMES = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for
    i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}`.
  - `WINDOWS_MAX_PATH = 260`.
  - `sanitize_path_component(name: str) -> str`: strip forbidden
    characters, strip trailing `.`/space, uppercase-compare the stem
    against `RESERVED_WINDOWS_NAMES` and prefix with `_` if reserved,
    raise `ValueError` only if the result is empty (e.g. input was all
    forbidden characters).
  - `exceeds_windows_path_limit(path: str) -> bool`: `len(path) >
    WINDOWS_MAX_PATH`.
  - `paths_collide(a: str, b: str) -> bool`: NFC-normalize both (reuse
    `core/paths.to_nfc`) then compare case-insensitively.

## 2. Models

- New `backend/app/models/destination_rule.py`:
  - `DestinationRule(SQLModel, table=True)`: `id`, `scan_id: int =
    Field(foreign_key="scan.id")`, `routing_group: str`,
    `destination_root: str`, `country_subfolder_enabled: bool = False`,
    `enabled: bool = True`. `__table_args__ = (UniqueConstraint("scan_id",
    "routing_group"),)`.
- New `backend/app/models/move_plan.py`:
  - `MOVE_PLAN_STATUSES = ("draft", "generated")`.
  - `MOVE_OPERATION_STATUSES = ("planned", "blocked")` — a module
    docstring note that Phase 15 appends the execution states.
  - `MovePlan(SQLModel, table=True)`: `id`, `scan_id: int =
    Field(foreign_key="scan.id")`, `status: str = "draft"`,
    `collision_policy: str = "error"`, `validation_mode: str =
    "standard"`, `created_at`, `approved_at: datetime | None = None`.
  - `MoveOperation(SQLModel, table=True)`: `id`, `move_plan_id: int =
    Field(foreign_key="moveplan.id")`, `scan_id: int`, `media_file_id:
    int = Field(foreign_key="mediafile.id")`, `source_path: str`,
    `planned_destination_path: str`, `actual_destination_path: str |
    None = None`, `source_size: int`, `source_hash: str | None = None`,
    `destination_size: int | None = None`, `destination_hash: str | None
    = None`, `status: str`, `started_at: datetime | None = None`,
    `finished_at: datetime | None = None`, `error_code: str | None =
    None`, `error_message: str | None = None`.
  - No `from __future__ import annotations` in either module — same
    `Relationship()`/PEP 563 constraint as Phase 3's models, even though
    these two don't need relationships yet, for consistency with the rest
    of `models/`.
- `backend/app/models/__init__.py`: add `DestinationRule`, `MovePlan`,
  `MoveOperation` to imports and `__all__`.

## 3. Repositories

- New `backend/app/repositories/destination_rule_repository.py`:
  `DestinationRuleRepository(Repository[DestinationRule])` +
  `list_by_scan(scan_id) -> Sequence[DestinationRule]`,
  `replace_for_scan(scan_id, rules: list[DestinationRule]) -> None`
  (delete existing rows for `scan_id`, insert the new set, single
  commit).
- New `backend/app/repositories/move_plan_repository.py`:
  `MovePlanRepository(Repository[MovePlan])` + `get_latest_for_scan(scan_id)
  -> MovePlan | None`.
- New `backend/app/repositories/move_operation_repository.py`:
  `MoveOperationRepository(Repository[MoveOperation])` +
  `list_by_plan(move_plan_id) -> Sequence[MoveOperation]`,
  `bulk_create(operations: list[MoveOperation]) -> None`.

## 4. Destinations service

- New `backend/app/services/destinations.py`:
  - `DestinationConfig` frozen dataclass: `destination_root: str`,
    `country_subfolder_enabled: bool`.
  - `set_destination_rules(session, scan_id: int, mapping:
    dict[str, DestinationConfig]) -> list[DestinationRule]`: validate every
    key is in `ROUTING_GROUPS` (raise `ValueError` listing the bad key
    otherwise — caught and reported by the CLI, not by this function),
    build one `DestinationRule` per mapping entry (`enabled=True`),
    `DestinationRuleRepository.replace_for_scan(...)`, return the rows.

## 5. Move-plan service

- New `backend/app/services/move_plan.py`:
  - `PlanValidationIssue` frozen dataclass: `error_code: str`,
    `error_message: str` (internal, folded into `MoveOperation` before
    returning).
  - `_build_destination_path(media_file, classification, rule) -> str`:
    `Path(rule.destination_root)`, append
    `sanitize_path_component(classification.country_name or
    classification.country_code or "unknown")` when
    `rule.country_subfolder_enabled`, append `media_file.file_name`;
    return NFC-normalized POSIX-style string via `core.paths.to_nfc`.
  - `_check_disk_space(operations: list[_PendingOp]) -> dict[str, int]`:
    group pending ops by destination volume root (`os.path.splitdrive`
    on Windows; `Path(...).anchor` fallback), sum `source_size`, compare
    each group total against `shutil.disk_usage(volume_root).free`;
    return `{volume_root: shortfall_bytes}` for any volume short (empty
    dict = all volumes OK).
  - `_check_locked(path: Path) -> bool`: `try: open(path, "r+b").close()
    except (PermissionError, OSError): return True`; `return False`.
  - `generate_move_plan(session, scan_id: int, *, collision_policy: str =
    "error", validation_mode: str = "standard", on_progress:
    Callable[[MediaFile, MoveOperation], None] | None = None) ->
    MovePlanSummary`:
    1. Load `Scan`; load `DestinationRuleRepository.list_by_scan(scan_id)`
       filtered to `enabled=True`, keyed by `routing_group`.
    2. Iterate `MediaFileRepository.list_by_scan(scan_id)`; for each, load
       its `Classification` via `ClassificationRepository
       .get_by_media_file_id`. Skip (count as `skipped_unclassified`) if
       none. Skip (count as `unmapped`) if
       `effective_routing_group` has no enabled rule.
    3. For the remaining candidates, build the destination path, then run
       validations in this order, stopping at the first failure per file
       (each maps to one `error_code`):
       - `SOURCE_MISSING` — `not Path(media_file.absolute_path).exists()`.
       - `SOURCE_CHANGED` — current `stat().st_size` /
         `st_mtime` differ from `media_file.size_bytes` /
         `media_file.modified_at`.
       - `SOURCE_LOCKED` — `_check_locked(...)`.
       - `SOURCE_EQUALS_DESTINATION` — NFC-normalized absolute source
         path equals the destination path.
       - `PATH_TOO_LONG` — `exceeds_windows_path_limit(destination_path)`.
       - `DUPLICATE_IN_PLAN` — another candidate in this same run already
         claimed a `paths_collide`-equal destination path.
       - `NAME_COLLISION` — a file already exists on disk at the
         destination path (`Path(destination_path).exists()`, which is
         inherently case-insensitive on the target NTFS/exFAT/APFS
         volumes) — with `collision_policy == "error"` (the only
         supported policy).
       - `DESTINATION_NOT_WRITABLE` — `os.access(Path(destination_root),
         os.W_OK)` is false, or the parent doesn't exist and can't be
         created per a dry `os.access` check on the nearest existing
         ancestor.
       A file with no failing check gets `status="planned"`; the first
       failing check sets `status="blocked"` with its `error_code`/
       `error_message` and skips the remaining checks for that file.
    4. Run `_check_disk_space` over every *currently-planned* (not
       blocked) candidate; any file whose destination volume is short
       gets flipped to `status="blocked"`, `error_code=
       "INSUFFICIENT_DISK_SPACE"`.
    5. Persist: create the `MovePlan` row (`status="generated"`), bulk
       create all `MoveOperation` rows via
       `MoveOperationRepository.bulk_create`, call `on_progress` per row.
    6. Return `MovePlanSummary` (frozen dataclass): `total_planned`,
       `total_blocked`, `total_bytes_planned`, `unmapped`,
       `skipped_unclassified`, `by_group: dict[str, int]`,
       `by_error_code: dict[str, int]`.

## 6. CLI wiring

- `backend/app/cli/main.py`:
  - `@app.command("destinations")` — `destinations_command(scan_id: int =
    typer.Option(..., "--scan-id"), config: Path = typer.Option(...,
    "--config", exists=True, dir_okay=False), database: Path | None =
    typer.Option(None, "--database", hidden=True))`: `json.loads` the
    config file into `{routing_group: {"destination_root": str,
    "country_subfolder_enabled": bool}}`, build `DestinationConfig`
    values, call `set_destination_rules`; on `ValueError` print the
    message and `raise typer.Exit(code=1)`; otherwise print one line per
    mapped group.
  - `@app.command("plan")` — `plan_command(scan_id: int =
    typer.Option(..., "--scan-id"), collision_policy: str =
    typer.Option("error", "--collision-policy"), validation_mode: str =
    typer.Option("standard", "--validation-mode"), database: Path | None
    = typer.Option(None, "--database", hidden=True))`: reject a
    `collision_policy` other than `"error"` up front (`typer.Exit(1)`,
    README §17.5 — only `error` is implemented); call
    `generate_move_plan`; print `"DRY RUN — no files were moved."`
    followed by the summary (planned/blocked counts, total bytes,
    by-group, by-error-code breakdown).

## 7. Tests

- `backend/tests/unit/test_destination_paths.py`: `sanitize_path_component`
  strips forbidden characters, trailing dot/space, rewrites each reserved
  name (`CON`, `COM1`, `LPT9`, …); `exceeds_windows_path_limit` true/false
  at the 260 boundary; `paths_collide` true for `Foto.jpg`/`foto.JPG` and
  for an NFC/NFD pair of the same accented name, false for genuinely
  different names.
- `backend/tests/unit/test_destinations_service.py`: valid mapping
  produces one `DestinationRule` per group; an unknown routing-group key
  raises `ValueError`; calling `set_destination_rules` twice for the same
  scan replaces rather than duplicates rows.
- `backend/tests/unit/test_move_plan_service.py` (temp-directory fixtures,
  synthetic `MediaFile`/`Classification` rows, no real scan needed):
  - Happy path: one file, one mapped group, no collisions →
    `status="planned"`, correct `planned_destination_path`.
  - **Case-only collision**: a real file pre-created at the
    case-differing destination path → `status="blocked"`,
    `error_code="NAME_COLLISION"`.
  - **Over-length path**: a destination root long enough that appending
    the file name exceeds 260 characters → `status="blocked"`,
    `error_code="PATH_TOO_LONG"`.
  - Two source files mapped to the same destination path →
    `DUPLICATE_IN_PLAN` on the second.
  - Source file deleted after being scanned →
    `SOURCE_MISSING`.
  - Source file's mtime/size changed after being scanned →
    `SOURCE_CHANGED`.
  - Source path equal to computed destination path → `SOURCE_EQUALS_DESTINATION`.
  - `_check_locked` monkeypatched to raise `PermissionError` →
    `SOURCE_LOCKED`.
  - `shutil.disk_usage` monkeypatched to return near-zero free space →
    `INSUFFICIENT_DISK_SPACE`.
  - `country_subfolder_enabled=True` → destination path includes the
    sanitized country segment; `False` → flat under `destination_root`.
  - A file whose group has no enabled `DestinationRule` → excluded,
    counted in `unmapped`.
  - A file with no `Classification` row → excluded, counted in
    `skipped_unclassified`.
  - No filesystem write occurs anywhere in this module: assert the temp
    destination tree is unchanged (no new files/dirs) after
    `generate_move_plan` runs, for both the happy path and every blocked
    case.
- `backend/tests/integration/test_plan_cli.py`: full `scan` → `classify`
  → `destinations` → `plan` pipeline over `backend/tests/fixtures/`
  (temp copy) into a temp destination tree covering every routing group
  present in the fixtures. Assert: CLI exits `0`; `MovePlan` +
  `MoveOperation` rows exist in the DB with expected counts; **no
  destination directory or file was created** (`Path(dest_root)` listing
  unchanged before/after); fixtures unchanged (SHA-256 comparison, same
  pattern as every prior integration test).

## 8. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
- `uv run media-organizer destinations --help` and
  `uv run media-organizer plan --help` run cleanly.
- Manual: run `scan` → `classify` → `destinations --config <sample.json>`
  → `plan` against `backend/tests/fixtures/` with a temp destination
  root; confirm the printed summary lists planned/blocked counts and
  that `Path(temp_destination_root).rglob("*")` is empty afterward (dry
  run — nothing created).
