from typing import Tuple

import rasterio
from affine import Affine
from pyproj import Transformer, CRS

class GeoReferencer:
    """
    A class to handle georeferencing operations,
    converting between pixel coordinates and geographic coordinates (longitude/latitude)
    using a given affine transform and coordinate reference system (CRS).
    """
    def __init__(self, transform: Affine, crs: CRS):
        """
        Initializes the GeoReferencer with a given affine transform and CRS.

        Args:
            transform (Affine): The affine transformation matrix for the raster.
            crs (CRS): The coordinate reference system of the raster.
        """
        self.transform = transform
        # Ensure the CRS is properly initialized from its WKT representation
        self.crs = CRS.from_wkt(crs.to_wkt())
        # transformer: map coordinates (meters) → geographic coordinates (longitude/latitude)
        self.toGeo = Transformer.from_crs(self.crs, self.crs.geodetic_crs, always_xy=True)
        # transformer: geographic coordinates → map coordinates
        self.fromGeo = Transformer.from_crs(self.crs.geodetic_crs, self.crs, always_xy=True)

    def pixelToCoordinates(self, px: int, py: int) -> Tuple[float, float]:
        """
        Converts pixel coordinates to geographic coordinates (longitude, latitude).

        Args:
            px (int): The x-coordinate (column) of the pixel.
            py (int): The y-coordinate (row) of the pixel.

        Returns:
            Tuple[float, float]: The geographic coordinates (longitude, latitude).
        """
        # Convert pixel coordinates to map coordinates (x, y)
        x, y = rasterio.transform.xy(self.transform, px, py)
        # Transform map coordinates to geographic coordinates
        lon, lat = self.toGeo.transform(x, y)
        return lon, lat

    def coordinatesToPixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """
        Converts geographic coordinates (longitude, latitude) to pixel coordinates.

        Args:
            lon (float): The longitude of the geographic coordinate.
            lat (float): The latitude of the geographic coordinate.

        Returns:
            Tuple[int, int]: The pixel coordinates (column, row) as integers.
        """
        # Transform geographic coordinates to map coordinates (x, y)
        x, y = self.fromGeo.transform(lon, lat)
        # Convert map coordinates to pixel coordinates
        py, px = rasterio.transform.rowcol(self.transform, x, y)
        return int(px), int(py)