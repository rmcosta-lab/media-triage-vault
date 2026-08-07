# Requirements — Phase 11: Offline country resolution

## Objective

Resolve a file's capture country fully offline from its GPS coordinates —
README §14 end to end: extract coordinates from whichever GPS-adjacent
field is present, validate them, look them up against a bundled country
polygon dataset via Shapely + `STRtree`, and return an ISO code + name, or
`unknown` for no GPS / ocean / unresolvable points. Coordinates never
appear in the CLI's default JSON export.

## Scope

### In

- `backend/data/geography/countries.geojson`: a minimized Natural Earth
  1:110m Admin-0 Countries dataset (public domain), stripped to
  `iso_a2`/`name` properties and 3-decimal-place coordinates (~189 KB,
  down from the 839 KB raw source — see Decisions for why this resolution
  and this trim are enough).
- `extract_coordinates(metadata: dict) -> Coordinates | None` (README
  §14.1): reads `GPSLatitude`/`GPSLongitude` first (ExifTool already
  normalizes EXIF/XMP/QuickTime GPS tags into these two generic tag names
  — the same normalization Phase 9 already relies on for `Make`/`Model`),
  falling back to parsing `LocationInformation` as an ISO 6709 string
  (`+35.6762+139.6503/`) when the numeric tags are absent — video
  containers that only carry the ISO 6709 atom.
- `is_valid_coordinates(lat, lon) -> bool` (README §14.2): the
  `-90..90`/`-180..180` range check.
- `CountryResolver`: loads the bundled GeoJSON once, builds an `STRtree`
  spatial index, and resolves `Coordinates -> CountryResolution`
  (`country_code`, `country_name`, `method`, `confidence`) via
  point-in-polygon (README §14.3).
- No GPS, invalid coordinates, or a point outside every polygon (ocean) →
  `country_code="unknown"` (README §14.4).
- A border-proximity check (README §14.5): a resolved point within ~5.5 km
  of its country's polygon boundary is still classified, but with a
  distinct `method` and a lower `confidence`, matching "coordenadas
  próximas a fronteiras... poderão exigir revisão."
- Fix: `backend/app/cli/scan_report.py`'s `inventory.json` export no
  longer includes raw `gps_latitude`/`gps_longitude` (README §14.4 "não
  mostrar latitude e longitude no relatório por padrão" — this is Phase
  11's first chance to enforce it, since Phase 7 shipped before this rule
  existed in scope).
- Unit tests: the Tokyo fixture case (`iphone_jpeg_gps.jpg`'s injected
  GPS, `35.6762, 139.6503` → `JP`) — the roadmap's literal done criterion
  — plus ocean and border cases per README §14.4/§14.5.

### Out (later phases)

- Wiring `CountryResolver` into a `Classification` row or the `classify`
  CLI — Phase 12, same boundary Phase 9/10 established for rules.
- An advanced-config flag to reveal coordinates in output (README §14.4
  allows one; no CLI surface exists yet to hang it on).
- XMP-specific parsing beyond what ExifTool's generic `GPSLatitude`/
  `GPSLongitude` tags already normalize — Phase 6 already extracts these
  through the same batch call every media_kind uses; no separate XMP
  reader is introduced.

## Source of truth

- README §14 "Identificação do país" (§14.1–§14.5), in full.
- `specs/roadmap.md` Phase 11 entry and its *Done when* criterion.
- `specs/mission.md` principle 1 (100% local/offline — no geocoding API,
  ever) and README §28 "não registrar coordenadas em logs comuns."
- `specs/tech-stack.md` — Shapely + `STRtree` over a bundled
  `countries.geojson`, the pinned decision this phase implements.
- Phase 6's `metadata.py`/`MediaMetadata` — the exact ExifTool tag names
  (`GPSLatitude`, `GPSLongitude`, `LocationInformation`) this phase reads
  from the same raw-tag `metadata: dict` shape Phase 9/10's rules use.
- `backend/tests/fixtures/generate_fixtures.py`'s `make_iphone_jpeg_with_gps`
  — the Tokyo coordinates already injected into `iphone_jpeg_gps.jpg`
  since Phase 2.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Dataset | Natural Earth 1:110m Admin-0 Countries, trimmed to `iso_a2`+`name`, coordinates rounded to 3 decimals | Public domain, no attribution required, no network call at runtime (downloaded once at development time — the same category of action as vendoring ExifTool in Phase 2). 110m resolution is intentionally coarse: this is country-level lookup, not survey-grade boundary work: raw file is 839 KB; trimming ~166 unused Natural Earth columns and rounding coordinates to ~111m precision (matching the source's own simplification) cuts it to ~189 KB — small enough to commit outright, per the project's "surface binary/data vendoring size before committing" convention. |
| Missing ISO code | Drop the feature | Two Natural Earth features (`N. Cyprus`, `Somaliland`) have no resolvable ISO 3166-1 alpha-2 code (contested territories) — a GPS point landing there falls through to a neighboring country's polygon or `unknown`, an acceptable edge case for offline country-level classification, not a geopolitical statement the MVP needs to take a position on. |
| GPS source priority | `GPSLatitude`/`GPSLongitude` (numeric, ExifTool `-n` output) first, ISO 6709 `LocationInformation` string second | Matches Phase 6's own extraction: ExifTool already folds EXIF, XMP, and QuickTime GPS tags into the same two generic tag names when given `-n`; only some video containers carry GPS solely as an ISO 6709 location atom with no separate lat/long tags, which is what the fallback covers. |
| Border proximity threshold | `0.05°` (~5.5 km) distance from the resolved polygon's boundary → `method="point_in_polygon_near_border"`, `confidence=0.75` instead of `1.0` | README §14.5 only says border-adjacent points "poderão exigir revisão" without a fixed distance; a small, documented threshold makes the behavior deterministic and testable rather than vague. `confidence`/`method` are stored (README §14.5's "o sistema deverá guardar o método e a confiança") for a later phase to decide what to do with them. |
| `inventory.json` GPS redaction | Drop `gps_latitude`/`gps_longitude` from `_media_metadata_to_dict` entirely (not just null them) | README §14.4 is explicit ("não mostrar... por padrão") and §28 repeats it ("não registrar coordenadas em logs comuns"); dropping the keys outright is the simplest way to guarantee they never leak into the one report artifact that exists so far (Phase 13's HTML/CSV reports will need the same discipline when they land). |
| Module location | `backend/app/services/country.py` | Country resolution isn't a routing-priority rule (README §15) — it produces a separate dimension (`capture_country_code`, `specs/mission.md` #5) — so it belongs with `metadata.py`/`media_type.py` in `services/`, not `rules/`. |

## Constraints

- **100% local and offline** (`specs/mission.md` #1): the bundled GeoJSON
  is read from disk; no geocoding API, no network call, ever, at runtime.
- **No coordinates in default output** (README §14.4, §28): enforced in
  this phase's `inventory.json` fix; any future report surface must repeat
  this check.
- **Deterministic rules first** (`specs/mission.md` #6): point-in-polygon
  and range validation only — no fuzzy/heuristic country guessing (no
  timezone, folder name, or IP inference — README §14.4 rules these out
  explicitly).
