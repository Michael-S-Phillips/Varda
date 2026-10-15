"""Planetary bodies for the find-data map: footprints are longitude and
latitude on a body, and a basemap image is reprojected to that body's
geographic coordinates for display."""

from __future__ import annotations

import geopandas as gpd
from pyproj import CRS

from varda.common.parameter import LabeledEnum

# Mean radii (m), as the IAU reports them; enough for drawing a map
RADII_M = {
    "Mercury": 2_439_400.0,
    "Venus": 6_051_800.0,
    "Earth": 6_371_008.8,
    "Moon": 1_737_400.0,
    "Mars": 3_389_500.0,
    "Phobos": 11_080.0,
    "Ceres": 469_700.0,
    "Vesta": 262_700.0,
    "Io": 1_821_490.0,
    "Europa": 1_560_800.0,
    "Ganymede": 2_631_200.0,
    "Callisto": 2_410_300.0,
    "Enceladus": 252_100.0,
    "Titan": 2_574_730.0,
}


def bodyName(name: str) -> str:
    """A body's name as Varda writes it ("mars" → "Mars")."""
    for known in RADII_M:
        if known.lower() == name.strip().lower():
            return known
    return name.strip().title()


def geographicCrs(body: str) -> str:
    """The body's geographic (longitude, latitude) coordinate system, as a
    PROJ string; WGS 84 for Earth."""
    body = bodyName(body)
    if body == "Earth":
        return "EPSG:4326"
    radius = RADII_M.get(body)
    if radius is None:
        raise ValueError(f"Varda doesn't know {body}'s size.")
    return f"+proj=longlat +R={radius:g} +no_defs"


def normalizeLongitude(longitude: float) -> float:
    """-180 to 180, east positive (0-360 longitudes are converted)."""
    return ((longitude + 180.0) % 360.0) - 180.0


class BodyChoice(LabeledEnum):
    """A body chosen by hand, or found from a file's coordinate system
    (GeoJSON always says Earth's, even for Mars coordinates)."""

    AUTO = "From the file"
    MERCURY = "Mercury"
    VENUS = "Venus"
    EARTH = "Earth"
    MOON = "Moon"
    MARS = "Mars"
    CERES = "Ceres"
    VESTA = "Vesta"
    IO = "Io"
    EUROPA = "Europa"
    GANYMEDE = "Ganymede"
    CALLISTO = "Callisto"
    ENCELADUS = "Enceladus"
    TITAN = "Titan"


def bodyOf(crs: CRS | None) -> str:
    """The body a coordinate system belongs to, by its radius (within 1%)."""
    if crs is None:
        return "Earth"
    ellipsoid = crs.ellipsoid
    radius = ellipsoid.semi_major_metre if ellipsoid is not None else None
    if crs.to_epsg() == 4326 or radius is None:
        return "Earth"
    for name, known in RADII_M.items():
        if abs(radius - known) / known < 0.01:
            return name
    return "Earth"


def toLongitudeLatitude(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """A GeoDataFrame in longitude and latitude: geographic coordinates are
    taken as they are (degrees on whatever body; GeoJSON always declares
    Earth's), projected ones are converted on their own body."""
    crs = frame.crs
    if crs is None or crs.is_geographic:
        return frame
    return frame.to_crs(geographicCrs(bodyOf(crs)))
