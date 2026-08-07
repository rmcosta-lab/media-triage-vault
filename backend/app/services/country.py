"""Offline country resolution — README §14 "Identificação do país", roadmap Phase 11.

GPS coordinates never leave the machine and never reach an external
geocoding API (`specs/mission.md` #1) — the country lookup is a bundled
GeoJSON polygon set indexed with Shapely's `STRtree`, per
`specs/tech-stack.md`'s pinned decision.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry
from shapely.strtree import STRtree

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_COUNTRIES_GEOJSON_PATH = _REPO_ROOT / "backend" / "data" / "geography" / "countries.geojson"

UNKNOWN_COUNTRY_CODE = "unknown"
BORDER_PROXIMITY_DEGREES = 0.05

# ISO 6709 e.g. "+35.6762+139.6503/" or "+35.6762+139.6503+123.4/" (README §14.1).
_ISO_6709_PATTERN = re.compile(r"^(?P<lat>[+-]\d+(?:\.\d+)?)(?P<lon>[+-]\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class Coordinates:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class CountryResolution:
    country_code: str
    country_name: str | None
    method: str
    confidence: float


def is_valid_coordinates(latitude: float, longitude: float) -> bool:
    """README §14.2 — validity range."""
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def parse_iso6709(text: str | None) -> Coordinates | None:
    """Parse an ISO 6709 location string into ``Coordinates``, or ``None``."""
    if not text:
        return None
    match = _ISO_6709_PATTERN.match(text.strip())
    if not match:
        return None
    try:
        latitude = float(match.group("lat"))
        longitude = float(match.group("lon"))
    except ValueError:
        return None
    return Coordinates(latitude=latitude, longitude=longitude)


def extract_coordinates(metadata: dict[str, Any]) -> Coordinates | None:
    """README §14.1 — numeric GPS tags first, ISO 6709 location string fallback.

    ExifTool's ``-n`` output already folds EXIF, XMP, and QuickTime GPS
    tags into the generic ``GPSLatitude``/``GPSLongitude`` names (Phase 6);
    only some video containers carry GPS solely as an ISO 6709 atom.
    """
    latitude = metadata.get("GPSLatitude")
    longitude = metadata.get("GPSLongitude")
    if isinstance(latitude, int | float) and isinstance(longitude, int | float):
        if is_valid_coordinates(float(latitude), float(longitude)):
            return Coordinates(latitude=float(latitude), longitude=float(longitude))
        return None

    parsed = parse_iso6709(metadata.get("LocationInformation"))
    if parsed is not None and is_valid_coordinates(parsed.latitude, parsed.longitude):
        return parsed
    return None


class CountryResolver:
    """Loads the bundled country polygons once and resolves points against them."""

    def __init__(self, geojson_path: Path = DEFAULT_COUNTRIES_GEOJSON_PATH) -> None:
        with geojson_path.open(encoding="utf-8") as geojson_file:
            data = json.load(geojson_file)

        self._geometries: list[BaseGeometry] = []
        self._properties: list[dict[str, Any]] = []
        for feature in data["features"]:
            self._geometries.append(shape(feature["geometry"]))
            self._properties.append(feature["properties"])
        self._tree = STRtree(self._geometries)

    def resolve(self, coordinates: Coordinates | None) -> CountryResolution:
        """README §14.3/§14.4/§14.5 — point-in-polygon, with unknown/border handling."""
        if coordinates is None:
            return CountryResolution(
                country_code=UNKNOWN_COUNTRY_CODE,
                country_name=None,
                method="no_gps",
                confidence=0.0,
            )

        point = Point(coordinates.longitude, coordinates.latitude)
        for index in self._tree.query(point):
            geometry = self._geometries[index]
            if not (geometry.contains(point) or geometry.intersects(point)):
                continue

            properties = self._properties[index]
            distance_to_boundary = geometry.boundary.distance(point)
            if distance_to_boundary < BORDER_PROXIMITY_DEGREES:
                return CountryResolution(
                    country_code=properties["iso_a2"],
                    country_name=properties["name"],
                    method="point_in_polygon_near_border",
                    confidence=0.75,
                )
            return CountryResolution(
                country_code=properties["iso_a2"],
                country_name=properties["name"],
                method="point_in_polygon",
                confidence=1.0,
            )

        return CountryResolution(
            country_code=UNKNOWN_COUNTRY_CODE,
            country_name=None,
            method="no_polygon_match",
            confidence=0.0,
        )


@lru_cache(maxsize=1)
def get_default_resolver() -> CountryResolver:
    return CountryResolver()
