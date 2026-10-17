"""ROIs from masks: the pixels of a threshold (a band inside or outside a
range) or of a mask image become ROIs, one per connected region, sharing a
class name (an ROI class is a shared name). No Qt.

Varda's ROIs are simple polygons, so a region's holes are filled; specks
smaller than ``minPixels`` are dropped, and at most ``maxRegions`` of the
largest regions are kept, so a noisy threshold doesn't make thousands.
"""

from __future__ import annotations

import numpy as np
import rasterio.features
import shapely
from shapely.affinity import affine_transform
from shapely.geometry import Polygon, shape

from varda.common.entities import Color, ROIMode, VardaRaster
from varda.rois.roi_collection import ROICollection

MAX_REGIONS = 1000


def maskRegions(
    mask: np.ndarray, minPixels: int = 1, maxRegions: int = MAX_REGIONS
) -> list[Polygon]:
    """Each connected region of a (rows, cols) mask as a polygon in pixel
    coordinates (x = column), largest first; holes filled."""
    shapes = rasterio.features.shapes(
        np.asarray(mask, dtype=np.uint8), mask=np.asarray(mask, dtype=bool)
    )
    regions = [
        (shape(geometry).area, Polygon(shape(geometry).exterior))
        for geometry, value in shapes
        if value == 1
    ]
    regions = [r for r in regions if r[0] >= minPixels]
    regions.sort(key=lambda r: r[0], reverse=True)
    return [polygon for _, polygon in regions[:maxRegions]]


def addMaskAsRois(
    rois: ROICollection,
    mask: np.ndarray,
    image: VardaRaster,
    name: str,
    color: Color,
    minPixels: int = 1,
    maxRegions: int = MAX_REGIONS,
) -> tuple[int, int]:
    """Add a mask's regions (on ``image``'s pixel grid) to ``rois`` as the
    class ``name``; returns how many regions were added and how many were
    left out (too small, or past ``maxRegions``)."""
    everything = maskRegions(mask, 1, len(np.flatnonzero(mask)) or 1)
    kept = [r for r in everything if r.area >= minPixels][:maxRegions]
    t = image.transform
    for polygon in kept:
        if rois.crs is not None:  # the collection is in map coordinates
            polygon = affine_transform(polygon, [t.a, t.b, t.d, t.e, t.c, t.f])
        rois.addROI(shapely.make_valid(polygon), name, color, ROIMode.POLYGON)
    return len(kept), len(everything) - len(kept)


def thresholdMask(
    image: VardaRaster, band: int, low: float, high: float, inside: bool = True
) -> np.ndarray:
    """Pixels whose ``band`` (0-based) is inside (or outside) ``low``-``high``,
    inclusive; never pixels without data."""
    raw = image.getBands([band])
    values = np.ma.filled(np.ma.asarray(raw, dtype=np.float64), np.nan)[..., 0]
    nodata = image.bandModel.noData
    if nodata is not None and np.isfinite(nodata):
        values[values == nodata] = np.nan
    low, high = sorted((low, high))
    within = (values >= low) & (values <= high)
    return (within if inside else ~within) & np.isfinite(values)
