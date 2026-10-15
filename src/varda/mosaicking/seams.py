"""Where each image takes over in an overlap.

By default the stack order decides (the top image wins everywhere it has
data). A seam method instead splits each overlap between the two images,
pairwise in stack order:

- **Voronoi:** each overlap pixel goes to the image whose own edge is
  farther away, splitting the overlap down its middle (as ENVI's automatic
  seamlines do).
- **Least difference:** a minimum-cost path through |A - B| along the
  overlap's long axis (``skimage.graph.route_through_array``), so the seam
  follows where the images agree and is hard to see; each side goes to the
  image whose own part of the scene it touches.

The split is computed on a reduced copy of the overlap and kept as polygons
in map coordinates (the area the lower image takes), so it renders the same
at any resolution and can be edited by hand.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
from affine import Affine
from scipy import ndimage
from skimage.graph import route_through_array
from skimage.measure import approximate_polygon, find_contours

from varda.mosaicking.grid import TargetGrid, overlapGrid
from varda.mosaicking.model import MosaicInput, MosaicProject
from varda.mosaicking.recipe import Seam, SeamMethod
from varda.mosaicking.render import Resampling, readCube, sampleOnGrid

__all__ = ["Seam", "SeamMethod", "computeSeams"]

SEAM_PIXELS = 4_000_000  # seams are found on overlaps reduced to this many pixels
SIMPLIFY = 0.75  # polygon simplification tolerance, in seam-grid pixels
MIN_OVERLAP = 4  # overlaps fewer pixels across than this get no seam


def computeSeams(
    project: MosaicProject,
    method: SeamMethod,
    progress: Callable[[float, str], None] = lambda fraction, message: None,
) -> list[Seam]:
    """The seams between every pair of overlapping (visible) inputs, upper
    image first. Reads the project without changing it."""
    if method is SeamMethod.PRIORITY:
        return []
    inputs = [i for i in project.inputs if i.visible]
    pairs = [(a, b) for n, a in enumerate(inputs) for b in inputs[n + 1 :]]
    cubes: dict[int, np.ndarray] = {}
    seams = []
    for done, (top, bottom) in enumerate(pairs):
        progress(done / max(len(pairs), 1), "finding seams")
        coarse = _seamGrid(project, top.key, bottom.key)
        if coarse is None:
            continue
        a, b = (_sample(item, coarse, cubes) for item in (top, bottom))
        # sampleOnGrid empties pixels without data; others may miss a band
        validA = np.asarray(np.isfinite(a).any(axis=2))
        validB = np.asarray(np.isfinite(b).any(axis=2))
        both = validA & validB
        if min(coarse.width, coarse.height) < MIN_OVERLAP or not both.any():
            continue
        if method is SeamMethod.VORONOI:
            bottomWins = _voronoi(validA, validB)
        else:
            bottomWins = _leastDifference(a, b, validA, validB)
        # The bottom image's own part goes in its area too, so the outline
        # runs clear of the overlap's edge (the top image has no data there)
        regions = _polygons((bottomWins & both) | (validB & ~validA), coarse)
        if regions:
            seams.append(Seam(top.key, bottom.key, regions))
    return seams


def _sample(
    item: MosaicInput, grid: TargetGrid, cubes: dict[int, np.ndarray]
) -> np.ndarray:
    if item.key not in cubes:
        cubes[item.key] = readCube(item)
    values = sampleOnGrid(item, cubes[item.key], grid, Resampling.NEAREST)
    if item.radiometry is not None:
        values = item.radiometry.apply(values)
    return values


def _seamGrid(project: MosaicProject, a: int, b: int) -> TargetGrid | None:
    """A grid over the overlap and a margin around it (half the overlap's
    short side), so each image's edge and its own part of the scene show;
    reduced to at most SEAM_PIXELS."""
    grid = overlapGrid(project, a, b)
    if grid is None:
        return None
    margin = max(MIN_OVERLAP, min(grid.width, grid.height) // 2)
    width, height = grid.width + 2 * margin, grid.height + 2 * margin
    step = max(1, math.ceil(math.sqrt(width * height / SEAM_PIXELS)))
    return TargetGrid(
        grid.transform * Affine.translation(-margin, -margin) * Affine.scale(step),
        max(width // step, 1),
        max(height // step, 1),
        grid.crs,
    )


def _distanceTo(area: np.ndarray) -> np.ndarray:
    """Each pixel's distance to the nearest pixel of ``area`` (inf if none)."""
    if not area.any():
        return np.full(area.shape, np.inf)
    return ndimage.distance_transform_edt(~area)


def _voronoi(validA: np.ndarray, validB: np.ndarray) -> np.ndarray:
    """Where the lower image's own part of the scene is nearer than the
    upper one's: the overlap's middle, between the edge where one image
    ends and the other goes on. (Edges where both end don't count.)"""
    onlyA, onlyB = validA & ~validB, validB & ~validA
    return _distanceTo(onlyB) < _distanceTo(onlyA)


def _leastDifference(
    a: np.ndarray, b: np.ndarray, validA: np.ndarray, validB: np.ndarray
) -> np.ndarray:
    """Where the lower image takes over: beyond the cheapest path through
    the bands' (normalized) absolute difference, along the overlap's long
    axis."""
    both = validA & validB
    rows, cols = np.nonzero(both)
    top, bottom, left, right = rows.min(), rows.max(), cols.min(), cols.max()
    spread = np.nanstd(a[both], axis=0)
    spread = np.where(np.isfinite(spread) & (spread > 0), spread, 1.0)
    difference = np.mean(np.abs(np.nan_to_num(a - b)) / spread, axis=2)
    cost = np.where(both, difference + 1e-3, np.inf)  # a little length cost
    vertical = (bottom - top) >= (right - left)
    if vertical:
        first, last = top, bottom
        start = (first, int(np.nanargmin(np.where(both[first], cost[first], np.inf))))
        end = (last, int(np.nanargmin(np.where(both[last], cost[last], np.inf))))
    else:
        first, last = left, right
        start = (
            int(np.nanargmin(np.where(both[:, first], cost[:, first], np.inf))),
            first,
        )
        end = (int(np.nanargmin(np.where(both[:, last], cost[:, last], np.inf))), last)
    finite = np.where(
        np.isfinite(cost), cost, 1e6
    )  # route_through_array wants finite costs
    path, _ = route_through_array(
        finite, start, end, fully_connected=True, geometric=True
    )
    cut = np.zeros_like(both)
    for r, c in path:
        cut[r, c] = True
    # The overlap minus the path falls into pieces; each goes to the image
    # whose own (non-overlapping) part it touches, or by Voronoi otherwise
    pieces, count = ndimage.label(both & ~cut)
    onlyA, onlyB = validA & ~validB, validB & ~validA
    voronoi = _voronoi(validA, validB)
    bottomWins = np.zeros_like(both)
    for piece in range(1, count + 1):
        mask = pieces == piece
        near = ndimage.binary_dilation(mask, iterations=2)
        touchesA, touchesB = (near & onlyA).sum(), (near & onlyB).sum()
        if touchesB > touchesA or (touchesA == touchesB and voronoi[mask].mean() > 0.5):
            bottomWins |= mask
    return bottomWins


def _polygons(mask: np.ndarray, grid: TargetGrid) -> tuple[np.ndarray, ...]:
    """A mask's outlines as simplified polygons in map coordinates. The mask
    is padded so outlines close along the grid's border."""
    padded = np.pad(mask.astype(float), 1)
    polygons = []
    for contour in find_contours(padded, 0.5):
        contour = approximate_polygon(contour, SIMPLIFY) - 1.0  # undo the padding
        if len(contour) < 4:
            continue
        # contour points are (row, col) on pixel centers
        x, y = grid.transform * (contour[:, 1] + 0.5, contour[:, 0] + 0.5)
        polygons.append(np.column_stack([x, y]))
    return tuple(polygons)
