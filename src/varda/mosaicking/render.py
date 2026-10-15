"""Rendering a mosaic: every output pixel takes the value of the topmost
input that has valid data there (a hard seam by priority), read through
that input's correction. Nearest-neighbor resampling keeps every output
spectrum identical to a source pixel's. Alongside the mosaic comes the
source index: which input each pixel came from."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import shapely
from attrs import frozen
from scipy import ndimage

from varda.common.parameter import LabeledEnum
from varda.mosaicking.grid import TargetGrid
from varda.mosaicking.model import MosaicInput, MosaicProject
from varda.mosaicking.recipe import BlendMethod

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
    seams = _seamAreas(project, inputs)
    for start in range(0, grid.height, TILE_ROWS):
        rows = slice(start, min(start + TILE_ROWS, grid.height))
        progress(int(100 * start / grid.height), "rendering")
        if project.blend.method is not BlendMethod.NONE:
            _renderBlended(
                project,
                inputs,
                cubes,
                seams,
                grid,
                rows,
                resampling,
                bands,
                out,
                sources,
            )
            continue
        tile = out[rows].reshape(-1, count)
        tileSources = sources[rows].reshape(-1)
        if seams:
            _renderWithSeams(
                project,
                inputs,
                cubes,
                seams,
                grid,
                rows,
                resampling,
                bands,
                tile,
                tileSources,
            )
            out[rows] = tile.reshape(rows.stop - rows.start, grid.width, count)
            sources[rows] = tileSources.reshape(rows.stop - rows.start, grid.width)
            continue
        for item, cube in zip(inputs, cubes):
            todo = tileSources == NO_SOURCE
            if not todo.any():
                break
            cols, rowsIn = rawPixels(item, grid, rows, todo)
            values, valid = _sample(cube, cols, rowsIn, resampling)
            if item.radiometry is not None:
                values = item.radiometry.apply(values, bands)
            target = np.flatnonzero(todo)[valid]
            tile[target] = values[valid]
            tileSources[target] = project.inputs.index(item)
        out[rows] = tile.reshape(rows.stop - rows.start, grid.width, count)
        sources[rows] = tileSources.reshape(rows.stop - rows.start, grid.width)
    return MosaicResult(out, sources)


def _seamAreas(
    project: MosaicProject, inputs: list[MosaicInput]
) -> list[tuple[int, int, shapely.Geometry]]:
    """The seams between rendered inputs, as (top position, bottom position,
    the area the bottom one takes over), top first."""
    position = {item.key: n for n, item in enumerate(inputs)}
    areas = []
    for seam in project.seams:
        if seam.top in position and seam.bottom in position and seam.regions:
            area = shapely.union_all(
                [shapely.Polygon(r) for r in seam.regions if len(r) >= 3]
            )
            areas.append((position[seam.top], position[seam.bottom], area))
    return sorted(areas, key=lambda a: (a[0], a[1]))


def _ownership(
    inputs: list[MosaicInput],
    cubes: list[np.ndarray],
    seams: list[tuple[int, int, shapely.Geometry]],
    grid: TargetGrid,
    rows: slice,
    resampling: Resampling,
    bands: list[int] | None,
) -> tuple[list[np.ndarray], list[np.ndarray], np.ndarray]:
    """Every input sampled over ``rows`` (values and validity), and which one
    owns each pixel: the topmost valid one, then each seam hands its area to
    the lower input where that has data (-1 where none has)."""
    x, y = grid.pixelCenters(rows)
    samples, valids = [], []
    for item, cube in zip(inputs, cubes):
        cols, rowsIn = rawPixels(item, grid, rows)
        values, valid = _sample(cube, cols, rowsIn, resampling)
        if item.radiometry is not None:
            values = item.radiometry.apply(values, bands)
        samples.append(values)
        valids.append(valid)
    owner = np.full(len(x), NO_SOURCE, np.int64)
    for n in range(len(inputs) - 1, -1, -1):  # the topmost valid input wins
        owner[valids[n]] = n
    for top, bottom, area in seams:
        candidates = np.flatnonzero((owner == top) & valids[bottom])
        if candidates.size:
            inside = shapely.contains_xy(area, x[candidates], y[candidates])
            owner[candidates[inside]] = bottom
    return samples, valids, owner


def _renderWithSeams(
    project: MosaicProject,
    inputs: list[MosaicInput],
    cubes: list[np.ndarray],
    seams: list[tuple[int, int, shapely.Geometry]],
    grid: TargetGrid,
    rows: slice,
    resampling: Resampling,
    bands: list[int] | None,
    tile: np.ndarray,
    tileSources: np.ndarray,
) -> None:
    """One tile with seams: each pixel from its owner."""
    samples, _, owner = _ownership(inputs, cubes, seams, grid, rows, resampling, bands)
    for n, values in enumerate(samples):
        mine = owner == n
        tile[mine] = values[mine]
        tileSources[mine] = project.inputs.index(inputs[n])


# --- blending (visual) -------------------------------------------------------------


def _blendScale(project: MosaicProject, grid: TargetGrid) -> float:
    """Grid pixels per finest-input pixel (blend sizes are in the latter)."""
    finest = min(i.pixelSize for i in project.inputs)
    return finest / float(np.hypot(grid.transform.a, grid.transform.d))


def _renderBlended(
    project: MosaicProject,
    inputs: list[MosaicInput],
    cubes: list[np.ndarray],
    seams: list[tuple[int, int, shapely.Geometry]],
    grid: TargetGrid,
    rows: slice,
    resampling: Resampling,
    bands: list[int] | None,
    out: np.ndarray,
    sources: np.ndarray,
) -> None:
    """One tile, blended across the owners' boundaries. The tile is worked
    on with a margin of rows, as far as the blend reaches, so tiles join
    seamlessly."""
    blend, scale = project.blend, _blendScale(project, grid)
    if blend.method is BlendMethod.FEATHER:
        width = max(1.0, blend.width * scale)
        margin = int(np.ceil(width)) + 1
    else:
        levels = max(1, blend.levels + int(np.floor(np.log2(min(scale, 1.0)) + 1e-9)))
        margin = 2 ** (levels + 2)
    padded = slice(max(0, rows.start - margin), min(grid.height, rows.stop + margin))
    samples, valids, owner = _ownership(
        inputs, cubes, seams, grid, padded, resampling, bands
    )
    shape = (padded.stop - padded.start, grid.width)
    if blend.method is BlendMethod.FEATHER:
        blended = _feather(samples, valids, owner, shape, width)
    else:
        blended = _multiband(samples, valids, owner, shape, levels)
    keep = slice(rows.start - padded.start, rows.stop - padded.start)
    out[rows] = blended[keep]
    owners = owner.reshape(shape)[keep]
    positions = np.array([project.inputs.index(item) for item in inputs] + [NO_SOURCE])
    sources[rows] = positions[owners]  # -1 indexes the trailing NO_SOURCE


def _insideDistance(mask: np.ndarray) -> np.ndarray:
    """Distance from each pixel of ``mask`` to the nearest pixel outside it
    (inf when the mask has no outside)."""
    if mask.all():
        return np.full(mask.shape, np.inf)
    return ndimage.distance_transform_edt(mask)


def _feather(
    samples: list[np.ndarray],
    valids: list[np.ndarray],
    owner: np.ndarray,
    shape: tuple[int, int],
    width: float,
) -> np.ndarray:
    """Each input weighted by its signed distance to its ownership boundary,
    ramping from 0 to 1 over ``width`` pixels centered on it."""
    count = samples[0].shape[1]
    total = np.zeros((owner.size, count))
    weights = np.zeros(owner.size)
    for n, (values, valid) in enumerate(zip(samples, valids)):
        mine = (owner == n).reshape(shape)
        if not mine.any():
            continue
        signed = np.where(
            mine, _insideDistance(mine) - 0.5, 0.5 - _insideDistance(~mine)
        ).ravel()
        weight = np.clip(0.5 + signed / width, 0.0, 1.0) * valid
        total += weight[:, None] * np.nan_to_num(values)
        weights += weight
    with np.errstate(invalid="ignore", divide="ignore"):
        blended = np.where(weights[:, None] > 0, total / weights[:, None], np.nan)
    return blended.reshape(*shape, count).astype(np.float32)


def _down(image: np.ndarray) -> np.ndarray:
    sigma = (1.0, 1.0) + (0.0,) * (image.ndim - 2)
    return ndimage.gaussian_filter(image, sigma, mode="nearest")[::2, ::2]


def _up(image: np.ndarray, shape: tuple[int, ...]) -> np.ndarray:
    factors = [target / size for target, size in zip(shape, image.shape)]
    expanded = ndimage.zoom(image, factors, order=1, mode="nearest", grid_mode=True)
    return expanded[tuple(slice(0, s) for s in shape)]


def _multiband(
    samples: list[np.ndarray],
    valids: list[np.ndarray],
    owner: np.ndarray,
    shape: tuple[int, int],
    levels: int,
) -> np.ndarray:
    """Burt-Adelson multi-band blending: each input's Laplacian pyramid,
    combined under the Gaussian pyramid of its ownership mask, so coarse
    detail mixes over a wide band and fine detail over a narrow one."""
    count = samples[0].shape[1]
    composite = np.full((owner.size, count), np.nan)
    for n, values in enumerate(samples):
        composite[owner == n] = values[owner == n]
    background = np.isnan(composite).any(axis=1)
    fill = np.nan_to_num(composite)
    accumulated: list[np.ndarray] | None = None
    norms: list[np.ndarray] | None = None
    for n, (values, valid) in enumerate(zip(samples, valids)):
        mine = owner == n
        if not mine.any():
            continue
        # Outside its data an input takes the composite, so its pyramid has
        # no holes (and nothing foreign leaks in where it's weighted)
        image = np.where(valid[:, None], np.nan_to_num(values), fill).reshape(
            *shape, count
        )
        mask = mine.reshape(shape).astype(np.float64)
        gaussians, masks = [image], [mask]
        for _ in range(levels):
            gaussians.append(_down(gaussians[-1]))
            masks.append(_down(masks[-1]))
        laplacians = [
            g - _up(gaussians[k + 1], g.shape) for k, g in enumerate(gaussians[:-1])
        ] + [gaussians[-1]]
        weighted = [m[..., None] * band for m, band in zip(masks, laplacians)]
        if accumulated is None or norms is None:
            accumulated, norms = weighted, masks
        else:
            accumulated = [a + w for a, w in zip(accumulated, weighted)]
            norms = [a + m for a, m in zip(norms, masks)]
    if accumulated is None or norms is None:
        return np.full((*shape, count), np.nan, np.float32)
    levelsBlended = [
        a / np.maximum(m, 1e-9)[..., None] for a, m in zip(accumulated, norms)
    ]
    image = levelsBlended[-1]
    for level in reversed(levelsBlended[:-1]):
        image = _up(image, level.shape) + level
    image = image.reshape(-1, count)
    image[background] = np.nan
    return image.reshape(*shape, count).astype(np.float32)
