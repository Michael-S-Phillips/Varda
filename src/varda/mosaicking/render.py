"""Rendering a mosaic: every output pixel takes the value of the topmost
input that has valid data there (a hard seam by priority), read through
that input's correction. Nearest-neighbor resampling keeps every output
spectrum identical to a source pixel's. Alongside the mosaic comes the
source index: which input each pixel came from."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from attrs import frozen
from scipy import ndimage

from varda.common.parameter import LabeledEnum
from varda.mosaicking.grid import TargetGrid
from varda.mosaicking.model import MosaicInput, MosaicProject
from varda.mosaicking.transforms import applyMatrix

TILE_ROWS = 256
NO_SOURCE = -1


class Resampling(LabeledEnum):
    NEAREST = "Nearest neighbor (keeps spectra exact)"
    BILINEAR = "Bilinear (smoother; visual)"


@frozen
class MosaicResult:
    cube: np.ndarray  # (rows, cols, bands) float32, NaN where no input covers
    sources: (
        np.ndarray
    )  # (rows, cols) int16: position of the input in the stack, -1 = none


def _cube(item: MosaicInput, bands: list[int] | None) -> np.ndarray:
    image = item.image
    data = image.getData(bandIndices=bands) if bands is not None else image.getData()
    cube = np.ma.filled(np.ma.asarray(data, dtype=np.float32), np.nan)
    if image.nodata is not None:
        cube[cube == image.nodata] = np.nan
    return cube


def _sample(
    cube: np.ndarray, cols: np.ndarray, rows: np.ndarray, resampling: Resampling
) -> tuple[np.ndarray, np.ndarray]:
    """Values (N, bands) at continuous pixel coordinates, and whether each
    lands inside the image with every band valid."""
    height, width, bands = cube.shape
    if resampling is Resampling.NEAREST:
        c, r = np.floor(cols).astype(np.int64), np.floor(rows).astype(np.int64)
        inside = (c >= 0) & (c < width) & (r >= 0) & (r < height)
        values = np.full((len(cols), bands), np.nan, np.float32)
        values[inside] = cube[r[inside], c[inside]]
    else:
        # pixel centers sit at +0.5; map_coordinates indexes centers
        inside = (
            (cols >= 0.5)
            & (cols <= width - 0.5)
            & (rows >= 0.5)
            & (rows <= height - 0.5)
        )
        coordinates = np.vstack([rows[inside] - 0.5, cols[inside] - 0.5])
        values = np.full((len(cols), bands), np.nan, np.float32)
        for band in range(bands):
            values[inside, band] = ndimage.map_coordinates(
                cube[:, :, band], coordinates, order=1, mode="nearest", cval=np.nan
            )
    valid = inside & np.isfinite(values).all(axis=1)
    return values, valid


def readCube(item: MosaicInput, bands: list[int] | None = None) -> np.ndarray:
    """An input's data as float32 (rows, cols, bands), NaN where no-data."""
    return _cube(item, bands)


def sampleOnGrid(
    item: MosaicInput,
    cube: np.ndarray,
    grid: TargetGrid,
    resampling: Resampling = Resampling.BILINEAR,
) -> np.ndarray:
    """One input (its ``cube``, read with ``readCube``) resampled onto
    ``grid`` through its correction: (rows, cols, bands), NaN off the image."""
    out = np.full((grid.height, grid.width, cube.shape[2]), np.nan, np.float32)
    inverse = np.linalg.inv(item.correction)
    pixelFromMap = ~item.image.transform
    for start in range(0, grid.height, TILE_ROWS):
        rows = slice(start, min(start + TILE_ROWS, grid.height))
        x, y = grid.pixelCenters(rows)
        mapped = applyMatrix(inverse, np.column_stack([x, y]))
        cols, rowsIn = pixelFromMap * (mapped[:, 0], mapped[:, 1])
        values, valid = _sample(cube, np.asarray(cols), np.asarray(rowsIn), resampling)
        values[~valid] = np.nan
        out[rows] = values.reshape(rows.stop - rows.start, grid.width, -1)
    return out


def renderMosaic(
    project: MosaicProject,
    grid: TargetGrid,
    resampling: Resampling = Resampling.NEAREST,
    progress: Callable[[int, str], None] = lambda percent, message: None,
    visibleOnly: bool = False,
    bands: list[int] | None = None,
    cache: dict[int, np.ndarray] | None = None,
) -> MosaicResult:
    """Render the mosaic on ``grid``: all bands, or just ``bands`` (a preview
    of the display bands, say). ``cache`` keeps each input's cube by key
    between calls (for previews, which re-render often)."""
    inputs = [i for i in project.inputs if i.visible or not visibleOnly]
    count = len(bands) if bands is not None else project.inputs[0].image.bandCount
    out = np.full((grid.height, grid.width, count), np.nan, np.float32)
    sources = np.full((grid.height, grid.width), NO_SOURCE, np.int16)
    progress(0, "reading images")
    cache = {} if cache is None else cache
    for item in inputs:
        if item.key not in cache:
            cache[item.key] = _cube(item, bands)
    cubes = [cache[item.key] for item in inputs]
    inverses = [np.linalg.inv(item.correction) for item in inputs]
    pixelFromMaps = [~item.image.transform for item in inputs]
    for start in range(0, grid.height, TILE_ROWS):
        rows = slice(start, min(start + TILE_ROWS, grid.height))
        progress(int(100 * start / grid.height), "rendering")
        x, y = grid.pixelCenters(rows)
        tile = out[rows].reshape(-1, count)
        tileSources = sources[rows].reshape(-1)
        for item, cube, inverse, pixelFromMap in zip(
            inputs, cubes, inverses, pixelFromMaps
        ):
            todo = tileSources == NO_SOURCE
            if not todo.any():
                break
            mapped = applyMatrix(inverse, np.column_stack([x[todo], y[todo]]))
            cols, rowsIn = pixelFromMap * (mapped[:, 0], mapped[:, 1])
            values, valid = _sample(
                cube, np.asarray(cols), np.asarray(rowsIn), resampling
            )
            target = np.flatnonzero(todo)[valid]
            tile[target] = values[valid]
            tileSources[target] = project.inputs.index(item)
        out[rows] = tile.reshape(rows.stop - rows.start, grid.width, count)
        sources[rows] = tileSources.reshape(rows.stop - rows.start, grid.width)
    return MosaicResult(out, sources)
