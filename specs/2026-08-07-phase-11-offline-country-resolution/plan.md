# Plan — Phase 11: Offline country resolution

## 1. Dependency

- `pyproject.toml`: add `shapely>=2.0.0` to `[project.dependencies]`.
- `uv sync` to lock it.

## 2. Bundled dataset

- Download Natural Earth 1:110m Admin-0 Countries GeoJSON (public domain)
  to a scratch location; run a one-time transform script that strips it to
  `iso_a2`/`name` properties, rounds coordinates to 3 decimals, and drops
  the two contested-territory features with no resolvable ISO code.
- Commit the result at `backend/data/geography/countries.geojson`
  (~189 KB). Verify its size before committing per the project's binary/
  data-vendoring convention.

## 3. Country resolution service

- New `backend/app/services/country.py`:
  - `_REPO_ROOT`-relative default path to `countries.geojson` (same
    pattern as `backend/app/core/db.py`/`tools.py`).
  - `UNKNOWN_COUNTRY_CODE = "unknown"`.
  - `BORDER_PROXIMITY_DEGREES = 0.05`.
  - `Coordinates` frozen dataclass: `latitude: float`, `longitude: float`.
  - `CountryResolution` frozen dataclass: `country_code: str`,
    `country_name: str | None`, `method: str`, `confidence: float`.
  - `is_valid_coordinates(latitude: float, longitude: float) -> bool` —
    README §14.2 range check.
  - `parse_iso6709(text: str | None) -> Coordinates | None` — regex
    `^(?P<lat>[+-]\d+(?:\.\d+)?)(?P<lon>[+-]\d+(?:\.\d+)?)`, returns
    `None` on no match or non-numeric groups.
  - `extract_coordinates(metadata: dict[str, Any]) -> Coordinates | None` —
    `GPSLatitude`/`GPSLongitude` numeric fields first (validated), then
    `parse_iso6709(metadata.get("LocationInformation"))` (also validated).
  - `class CountryResolver:` — `__init__(self, geojson_path: Path = DEFAULT_COUNTRIES_GEOJSON_PATH)`
    loads the GeoJSON once, builds `self._geometries`/`self._properties`/
    `self._tree` (Shapely `STRtree`).
    `resolve(self, coordinates: Coordinates | None) -> CountryResolution`:
    `None` → `method="no_gps"`; point-in-polygon miss → `method="no_polygon_match"`;
    hit within `BORDER_PROXIMITY_DEGREES` of the polygon boundary →
    `method="point_in_polygon_near_border"`, `confidence=0.75`; hit
    otherwise → `method="point_in_polygon"`, `confidence=1.0`.
  - `get_default_resolver() -> CountryResolver` — `functools.lru_cache(maxsize=1)`
    singleton so the GeoJSON is parsed once per process.

## 4. `inventory.json` GPS redaction fix

- `backend/app/cli/scan_report.py`: remove `gps_latitude`/`gps_longitude`
  from `_media_metadata_to_dict`'s returned dict.
- Update `backend/tests/unit/test_scan_report.py` to assert the keys are
  absent from the serialized metadata.

## 5. Tests

- `backend/tests/unit/test_country_resolution.py`:
  - `is_valid_coordinates` — in-range, out-of-range latitude, out-of-range
    longitude.
  - `parse_iso6709` — a valid string, a malformed string, `None` input.
  - `extract_coordinates` — numeric GPS fields present, ISO 6709 fallback,
    both absent, numeric fields present but out of range (falls through
    to `None`, doesn't crash).
  - `CountryResolver.resolve`:
    - Tokyo (`35.6762, 139.6503`) → `country_code="JP"` (roadmap done
      criterion, matches `iphone_jpeg_gps.jpg`'s injected GPS).
    - Mid-Pacific ocean point → `country_code="unknown"`,
      `method="no_polygon_match"`.
    - `None` coordinates → `country_code="unknown"`, `method="no_gps"`.
    - A near-border point (Strasbourg, `48.58, 7.75`) →
      `method="point_in_polygon_near_border"`, `confidence=0.75`.
    - An inland point far from any border → `method="point_in_polygon"`,
      `confidence=1.0`.
  - `get_default_resolver()` returns the same instance across calls
    (singleton behavior).

## 6. Verification

- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy backend`
- `uv run pytest`
