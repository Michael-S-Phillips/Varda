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

TILE_ROWS = 256
WARP_STEP = 8  # a warp is evaluated every this many output pixels, then interpolated
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


def rawPixels(
    item: MosaicInput, grid: TargetGrid, rows: slice, select: np.ndarray | None = None
) -> tuple[np.ndarray, np.ndarray]:
    """The input's pixel (col, row) coordinates under the grid's pixel
    centers in ``rows`` (or the ``select``ed ones of them). A warp is
    evaluated on a coarse lattice and interpolated: it's smooth, and exact
    evaluation of a spline at every pixel would be slow."""
    x, y = grid.pixelCenters(rows)
    if item.warp is None:
        points = (
            np.column_stack([x, y])
            if select is None
            else np.column_stack([x[select], y[select]])
        )
        raw = item.uncorrect(points)
    else:
        count = rows.stop - rows.start
        lattice_r = np.unique(np.append(np.arange(0, count, WARP_STEP), count - 1))
        lattice_c = np.unique(
            np.append(np.arange(0, grid.width, WARP_STEP), grid.width - 1)
        )
        cc, rr = np.meshgrid(lattice_c + 0.5, lattice_r + rows.start + 0.5)
        lx, ly = grid.transform * (cc.ravel(), rr.ravel())
        coarse = item.uncorrect(np.column_stack([lx, ly])).reshape(
            len(lattice_r), len(lattice_c), 2
        )
        allRows, allCols = np.meshgrid(
            np.arange(count), np.arange(grid.width), indexing="ij"
        )
        # fractional positions in the lattice, for linear interpolation
        fr = np.interp(allRows.ravel(), lattice_r, np.arange(len(lattice_r)))
        fc = np.interp(allCols.ravel(), lattice_c, np.arange(len(lattice_c)))
        if select is not None:
            fr, fc = fr[select], fc[select]
        raw = np.column_stack(
            [
                ndimage.map_coordinates(
                    coarse[:, :, k], [fr, fc], order=1, mode="nearest"
                )
                for k in range(2)
            ]
        )
    cols, rowsIn = ~item.image.transform * (raw[:, 0], raw[:, 1])
    return np.asarray(cols), np.asarray(rowsIn)


def sampleOnGrid(
    item: MosaicInput,
    cube: np.ndarray,
    grid: TargetGrid,
    resampling: Resampling = Resampling.BILINEAR,
) -> np.ndarray:
    """One input (its ``cube``, read with ``readCube``) resampled onto
    ``grid`` through its correction: (rows, cols, bands), NaN off the image."""
    out = np.full((grid.height, grid.width, cube.shape[2]), np.nan, np.float32)
    for start in range(0, grid.height, TILE_ROWS):
        rows = slice(start, min(start + TILE_ROWS, grid.height))
        cols, rowsIn = rawPixels(item, grid, rows)
        values, valid = _sample(cube, cols, rowsIn, resampling)
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
    for start in range(0, grid.height, TILE_ROWS):
        rows = slice(start, min(start + TILE_ROWS, grid.height))
        progress(int(100 * start / grid.height), "rendering")
        tile = out[rows].reshape(-1, count)
        tileSources = sources[rows].reshape(-1)
        for item, cube in zip(inputs, cubes):
            todo = tileSources == NO_SOURCE
            if not todo.any():
                break
            cols, rowsIn = rawPixels(item, grid, rows, todo)
            values, valid = _sample(cube, cols, rowsIn, resampling)
            target = np.flatnonzero(todo)[valid]
            tile[target] = values[valid]
            tileSources[target] = project.inputs.index(item)
        out[rows] = tile.reshape(rows.stop - rows.start, grid.width, count)
        sources[rows] = tileSources.reshape(rows.stop - rows.start, grid.width)
    return MosaicResult(out, sources)
