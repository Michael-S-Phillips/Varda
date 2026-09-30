"""Helpers for analyses that read a cube and write a raster."""

from __future__ import annotations

import logging

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


logger = logging.getLogger(__name__)

# Pixels missing more than this share of their bands are dropped rather than filled
MIN_VALID_BAND_FRACTION = 0.5
_FILL_CHUNK = 16_384


def validPixels(cube: np.ndarray, nodata: float | None) -> np.ndarray:
    """(rows, cols) mask of pixels that are finite and not nodata in every band."""
    valid = np.all(np.isfinite(cube), axis=2)
    if nodata is not None:
        valid &= np.all(cube != nodata, axis=2)
    return valid


def readCube(image: VardaRaster) -> tuple[np.ndarray, np.ndarray]:
    """The image as a float64 (rows, cols, bands) cube ready for analysis, and
    the (rows, cols) mask of usable pixels.

    Nodata becomes NaN; a pixel's missing bands are filled along its spectrum
    (see ``fillAlongSpectrum``) so that a bad band here and there does not
    knock the pixel out; pixels missing most of their bands stay NaN.
    """
    cube = np.array(image.getData(), dtype=np.float64, copy=True)
    if image.nodata is not None:
        cube[cube == image.nodata] = np.nan
    return fillAlongSpectrum(cube)


def fillAlongSpectrum(
    cube: np.ndarray, minValidFraction: float = MIN_VALID_BAND_FRACTION
) -> tuple[np.ndarray, np.ndarray]:
    """Fill NaN bands of each pixel by linear interpolation along its spectrum
    (the nearest value beyond the first/last finite band). Pixels with fewer
    than ``minValidFraction`` of their bands finite are set entirely to NaN
    and reported False in the returned (rows, cols) mask.

    A float64 input is modified in place (a cube can be several GB)."""
    data = np.asarray(cube, dtype=np.float64)
    rows, cols, bands = data.shape
    flat = data.reshape(-1, bands)
    finite = np.isfinite(flat)
    needed = max(1 if bands == 1 else 2, int(np.ceil(minValidFraction * bands)))
    valid = finite.sum(axis=1) >= needed
    flat[~valid] = np.nan

    toFill = np.flatnonzero(valid & ~finite.all(axis=1))
    idx = np.arange(bands)
    for start in range(0, toFill.size, _FILL_CHUNK):
        rowsToFill = toFill[start : start + _FILL_CHUNK]
        block, ok = flat[rowsToFill], finite[rowsToFill]
        # index of the previous / next finite band for every band position
        prevIdx = np.maximum.accumulate(np.where(ok, idx, -1), axis=1)
        nextRev = np.maximum.accumulate(np.where(ok[:, ::-1], idx, -1), axis=1)
        nextIdx = np.where(nextRev >= 0, bands - 1 - nextRev, -1)[:, ::-1]
        hasPrev, hasNext = prevIdx >= 0, nextIdx >= 0
        prevVal = np.take_along_axis(block, np.clip(prevIdx, 0, bands - 1), axis=1)
        nextVal = np.take_along_axis(block, np.clip(nextIdx, 0, bands - 1), axis=1)
        both = hasPrev & hasNext
        # (at finite positions prev == next: no gap to interpolate, avoid 0/0)
        span = np.where(both & (nextIdx > prevIdx), nextIdx - prevIdx, 1)
        weight = np.where(both, (idx - prevIdx) / span, 0.0)
        interpolated = np.where(
            both,
            prevVal + weight * (nextVal - prevVal),
            np.where(hasPrev, prevVal, nextVal),
        )
        flat[rowsToFill] = np.where(ok, block, interpolated)
    if toFill.size:
        logger.info(
            "Filled missing bands along the spectrum for %d of %d pixels",
            toFill.size,
            flat.shape[0],
        )
    return data, valid.reshape(rows, cols)


def bandIndex(image: VardaRaster, oneBased: int) -> int:
    """Clamp a user-facing 1-based band number to a valid 0-based index."""
    return int(np.clip(oneBased - 1, 0, image.bandCount - 1))


def singleBandRaster(
    image: VardaRaster,
    values: np.ndarray,
    *,
    name: str,
    bandName: str,
    units: str = "",
    description: str = "",
) -> VardaRaster:
    """A one-band raster over ``image``'s footprint and georeferencing."""
    source = ArrayDataSource(
        np.asarray(values, dtype=np.float32)[:, :, np.newaxis],
        wavelengths=np.array([bandName]),
        wavelengthUnits=units,
        bandNames=[bandName],
        transform=image.transform,
        crs=image.crs,
        description=description or f"{bandName} of {image.name}",
    )
    return VardaRaster(source, name=name)
