"""Helpers for analyses that read a cube and write a raster."""

from __future__ import annotations

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def validPixels(cube: np.ndarray, nodata: float | None) -> np.ndarray:
    """(rows, cols) mask of pixels that are finite and not nodata in every band."""
    valid = np.all(np.isfinite(cube), axis=2)
    if nodata is not None:
        valid &= np.all(cube != nodata, axis=2)
    return valid


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
