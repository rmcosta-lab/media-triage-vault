# Validation — Phase 11: Offline country resolution

### Functional

- [x] Tokyo fixture (`35.6762, 139.6503`) resolves to `JP` (roadmap done
      criterion) — `test_tokyo_resolves_to_japan`.
- [x] Border and ocean cases behave per README §14 (§14.4/§14.5): ocean →
      `unknown` (`test_ocean_point_resolves_to_unknown`); a border-adjacent
      point (Strasbourg, `48.58, 7.75`) resolves with a distinct
      `method`/lower `confidence` (`test_near_border_point_has_reduced_confidence`)
      vs. an inland point (`test_inland_point_has_full_confidence`).
- [x] No GPS → `unknown` — `test_no_coordinates_resolves_to_unknown`.
- [x] Coordinates outside the `-90..90`/`-180..180` range are rejected —
      `test_is_valid_coordinates_latitude_out_of_range`,
      `test_is_valid_coordinates_longitude_out_of_range`,
      `test_extract_coordinates_out_of_range_numeric_fields_returns_none`.
- [x] `inventory.json` no longer exposes raw `gps_latitude`/`gps_longitude`
      (nor `gps_position_raw`/`location_information`) —
      `test_write_inventory_json_nests_metadata_when_present` updated to
      assert their absence.

### Tests

- [x] Unit tests cover `is_valid_coordinates`, `parse_iso6709`,
      `extract_coordinates` (numeric-first, ISO 6709 fallback, both
      absent, out-of-range numeric) — see `test_country_resolution.py`.
- [x] Unit tests cover `CountryResolver.resolve` for Tokyo, ocean, no-GPS,
      near-border, and inland cases — `TestCountryResolverResolve`.
- [x] `test_scan_report.py` asserts GPS keys are absent from the exported
      metadata dict.

### Safety

- [x] No network call is made at runtime — `countries.geojson` is read
      from disk only; confirmed by reading `country.py` (only `json`,
      `re`, `shapely` imports — no `urllib`/`requests`/`httpx`). The
      dataset itself was downloaded once at development time (analogous
      to vendoring ExifTool in Phase 2), not fetched by the running app.
- [x] No coordinates appear in the CLI's default JSON export — confirmed
      by test and by reading `scan_report.py`'s `_media_metadata_to_dict`.

### Technical

- [x] `uv run ruff check .` clean — "All checks passed!".
- [x] `uv run ruff format --check .` clean — "59 files already formatted".
- [x] `uv run mypy backend` clean — "Success: no issues found in 59 source
      files" (added a `shapely.*` `ignore_missing_imports` override,
      mirroring the existing `pillow_heif` one — Shapely ships no inline
      type stubs).
- [x] `uv run pytest` green — 151 passed (18 new: 15 country-resolution
      unit tests, 1 updated `scan_report` test with 4 new assertions,
      2 additional passing tests carried over from the `MediaMetadata`
      round-trip fixture change).
- [x] `backend/data/geography/countries.geojson` size verified: 839 KB raw
      Natural Earth source trimmed to 192 KB after stripping unused
      columns and rounding coordinates to 3 decimals.
