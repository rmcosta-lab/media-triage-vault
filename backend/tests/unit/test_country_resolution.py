"""Unit tests for backend.app.services.country — README §14, see
specs/2026-08-07-phase-11-offline-country-resolution/plan.md and validation.md.
"""

from __future__ import annotations

from backend.app.services.country import (
    Coordinates,
    CountryResolver,
    extract_coordinates,
    get_default_resolver,
    is_valid_coordinates,
    parse_iso6709,
)

# Same coordinates injected into iphone_jpeg_gps.jpg since Phase 2
# (backend/tests/fixtures/generate_fixtures.py).
TOKYO_LATITUDE = 35.6762
TOKYO_LONGITUDE = 139.6503


def test_is_valid_coordinates_in_range() -> None:
    assert is_valid_coordinates(35.6762, 139.6503) is True


def test_is_valid_coordinates_latitude_out_of_range() -> None:
    assert is_valid_coordinates(95.0, 0.0) is False
    assert is_valid_coordinates(-95.0, 0.0) is False


def test_is_valid_coordinates_longitude_out_of_range() -> None:
    assert is_valid_coordinates(0.0, 185.0) is False
    assert is_valid_coordinates(0.0, -185.0) is False


def test_parse_iso6709_valid_string() -> None:
    result = parse_iso6709("+35.6762+139.6503/")
    assert result == Coordinates(latitude=35.6762, longitude=139.6503)


def test_parse_iso6709_malformed_returns_none() -> None:
    assert parse_iso6709("not a location") is None
    assert parse_iso6709(None) is None
    assert parse_iso6709("") is None


def test_extract_coordinates_numeric_fields_take_priority() -> None:
    metadata = {
        "GPSLatitude": TOKYO_LATITUDE,
        "GPSLongitude": TOKYO_LONGITUDE,
        "LocationInformation": "+0.0+0.0/",
    }
    result = extract_coordinates(metadata)
    assert result == Coordinates(latitude=TOKYO_LATITUDE, longitude=TOKYO_LONGITUDE)


def test_extract_coordinates_falls_back_to_iso6709() -> None:
    metadata = {"LocationInformation": "+35.6762+139.6503/"}
    result = extract_coordinates(metadata)
    assert result == Coordinates(latitude=TOKYO_LATITUDE, longitude=TOKYO_LONGITUDE)


def test_extract_coordinates_none_when_nothing_present() -> None:
    assert extract_coordinates({}) is None


def test_extract_coordinates_out_of_range_numeric_fields_returns_none() -> None:
    metadata = {"GPSLatitude": 999.0, "GPSLongitude": 139.6503}
    assert extract_coordinates(metadata) is None


def test_get_default_resolver_is_a_singleton() -> None:
    assert get_default_resolver() is get_default_resolver()


class TestCountryResolverResolve:
    resolver = CountryResolver()

    def test_tokyo_resolves_to_japan(self) -> None:
        result = self.resolver.resolve(
            Coordinates(latitude=TOKYO_LATITUDE, longitude=TOKYO_LONGITUDE)
        )
        assert result.country_code == "JP"
        assert result.country_name == "Japan"
        assert result.method == "point_in_polygon"
        assert result.confidence == 1.0

    def test_ocean_point_resolves_to_unknown(self) -> None:
        result = self.resolver.resolve(Coordinates(latitude=0.0, longitude=-160.0))
        assert result.country_code == "unknown"
        assert result.method == "no_polygon_match"
        assert result.confidence == 0.0

    def test_no_coordinates_resolves_to_unknown(self) -> None:
        result = self.resolver.resolve(None)
        assert result.country_code == "unknown"
        assert result.method == "no_gps"
        assert result.confidence == 0.0

    def test_near_border_point_has_reduced_confidence(self) -> None:
        result = self.resolver.resolve(Coordinates(latitude=48.58, longitude=7.75))
        assert result.country_code == "FR"
        assert result.method == "point_in_polygon_near_border"
        assert result.confidence == 0.75

    def test_inland_point_has_full_confidence(self) -> None:
        result = self.resolver.resolve(Coordinates(latitude=43.5, longitude=1.5))
        assert result.country_code == "FR"
        assert result.method == "point_in_polygon"
        assert result.confidence == 1.0
