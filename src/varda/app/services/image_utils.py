import logging

import numpy as np
import rasterio
from affine import Affine
from pyproj import Transformer, CRS

from varda.core.entities import Image, Stretch, Band

logger = logging.getLogger(__name__)

def getRasterFromBand(image: Image, band: Band):
    """Get a subset of the raster data for RGB display.

    Creates a 3-band subset of the raster data based on the RGB channels
    defined in the selected band configuration.

    Returns:
        np.ndarray: Array with shape (height, width, 3) for RGB display
    """

    try:
        # Get the RGB bands from the raster data
        rgb_data = image.raster[:, :, [band.r, band.g, band.b]]

        # Handle any out-of-range values
        if np.isnan(rgb_data).any():
            logger.warning(
                f"NaN values found in raster data for bands {[band.r, band.g, band.b]}"
            )
            rgb_data = np.nan_to_num(rgb_data)

        return rgb_data
    except IndexError as e:
        logger.error(f"Error extracting RGB bands: {e}")
        # Return a placeholder if there's an error
        h, w = image.raster.shape[0:2]
        return np.zeros((h, w, 3))


def transformPixelToGeoCoord(
    image: Image, px: int, py: int
) -> tuple[float, float]:
    """Transform pixel coordinates to geospatial coordinates.

    Args:
        image (Image): The image object containing geospatial metadata.
        px (int): The pixel x-coordinate.
        py (int): The pixel y-coordinate.

    Returns:
        tuple[float, float]: The transformed geospatial coordinates (longitude, latitude).
    """


    if not image.metadata.hasGeospatialData:
        raise ValueError(f"No geospatial data found for image {image}")

    transform = image.metadata.transform
    crs = image.metadata.crs

    # Convert pixel coordinates to map coordinates (x, y)
    mx, my = rasterio.transform.xy(transform, px, py)
    # Transform map coordinates to geographic coordinates
    toGeo = Transformer.from_crs(
        crs, crs.geodetic_crs, always_xy=True
    )
    lon, lat = toGeo.transform(mx, my)
    return lon, lat

