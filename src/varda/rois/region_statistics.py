"""Per-band statistics over an arbitrary pixel footprint of an image.

Used both by ROICollection (for stored ROIs) and by quick-look tools that
inspect a footprint without adding it to a collection.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import rasterio.features
from shapely.geometry import Polygon
from shapely.geometry import mapping as shapely_mapping

from varda.common.entities import VardaRaster


def boxPolygonPixels(
    centerCol: int, centerRow: int, width: int, height: int
) -> np.ndarray:
    """(4, 2) (col, row) pixel-corner polygon of a ``width`` x ``height`` box.

    Pixel ``c`` spans ``c..c+1``, so the polygon rasterises to exactly
    ``width * height`` pixels. Odd sizes are centred on the given pixel; even
    sizes extend one extra pixel to the right and down.
    """
    left = centerCol - (width - 1) // 2
    top = centerRow - (height - 1) // 2
    return np.array(
        [
            [left, top],
            [left + width, top],
            [left + width, top + height],
            [left, top + height],
        ],
        dtype=np.float64,
    )


def rasterizeFootprint(pixelPolygon: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Boolean mask of the pixels whose centres fall inside a (col, row) polygon."""
    polygon = Polygon([(float(c), float(r)) for c, r in pixelPolygon])
    mask = rasterio.features.rasterize(
        [(shapely_mapping(polygon), 1)], out_shape=shape, fill=0, dtype=np.uint8
    )
    return mask.astype(bool)


def computeRegionStatistics(
    pixelPolygon: np.ndarray, image: VardaRaster
) -> dict[str, npt.ArrayLike]:
    """Per-band mean/std/min/max and pixel_count of an image under a footprint.

    Reads only the footprint's bounding window. Nodata is treated per element
    (a pixel may be valid at most wavelengths but nodata at a few), and pixels
    with no valid band at all are dropped. An empty footprint yields zeros.
    """
    mask = rasterizeFootprint(pixelPolygon, (image.height, image.width))
    rows, cols = np.where(mask)
    if len(rows) == 0:
        return _emptyStatistics(image.bandCount)

    rMin, rMax = int(rows.min()), int(rows.max())
    cMin, cMax = int(cols.min()), int(cols.max())
    data = image.getData(
        bandIndices=None, window=(rMin, cMin, rMax - rMin + 1, cMax - cMin + 1)
    )
    subMask = mask[rMin : rMax + 1, cMin : cMax + 1]
    pixels = data[subMask].astype(np.float64)  # (n_pixels, bands)

    if image.nodata is not None:
        pixels[pixels == image.nodata] = np.nan
    pixels = pixels[~np.all(np.isnan(pixels), axis=1)]
    if len(pixels) == 0:
        return _emptyStatistics(data.shape[2] if data.ndim == 3 else 1)

    return {
        "mean": np.nanmean(pixels, axis=0).astype(np.float64),
        "std": np.nanstd(pixels, axis=0).astype(np.float64),
        "min": np.nanmin(pixels, axis=0),
        "max": np.nanmax(pixels, axis=0),
        "pixel_count": len(pixels),
    }


def _emptyStatistics(bandCount: int) -> dict[str, npt.ArrayLike]:
    return {
        "mean": np.zeros(bandCount),
        "std": np.zeros(bandCount),
        "min": np.zeros(bandCount),
        "max": np.zeros(bandCount),
        "pixel_count": 0,
    }
