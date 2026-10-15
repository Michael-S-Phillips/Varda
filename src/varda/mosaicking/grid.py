"""The grid a mosaic is rendered on: its map projection, pixel size and
extent (the union of the corrected inputs), snapped to whole pixels."""

from __future__ import annotations

import math

import numpy as np
from affine import Affine
from attrs import frozen
from rasterio.crs import CRS

from varda.mosaicking.model import MosaicProject


@frozen
class TargetGrid:
    transform: Affine  # output pixel (col, row) → map
    width: int
    height: int
    crs: CRS | None

    def pixelCenters(self, rows: slice) -> tuple[np.ndarray, np.ndarray]:
        """Map (x, y) of the pixel centers in ``rows`` (all columns)."""
        cols, rowIndex = np.meshgrid(
            np.arange(self.width) + 0.5, np.arange(rows.start, rows.stop) + 0.5
        )
        x, y = self.transform * (cols.ravel(), rowIndex.ravel())
        return np.asarray(x), np.asarray(y)


def pixelSize(project: MosaicProject) -> float:
    """The finest input pixel size (map units)."""
    return min(
        float(np.hypot(i.image.transform.a, i.image.transform.d))
        for i in project.inputs
    )


def defaultGrid(project: MosaicProject, resolution: float | None = None) -> TargetGrid:
    """A grid covering every input at the finest resolution (or ``resolution``),
    on the top input's pixel grid (so its pixels are copied exactly). North up
    when the inputs are georeferenced; otherwise rows run down, as in the
    images."""
    size = float(resolution) if resolution else pixelSize(project)
    corners = np.vstack([i.footprint() for i in project.inputs])
    anchor = project.inputs[0].footprint()[0]  # the top input's corner
    left = (
        anchor[0] + math.floor((corners[:, 0].min() - anchor[0]) / size + 1e-9) * size
    )
    right = (
        anchor[0] + math.ceil((corners[:, 0].max() - anchor[0]) / size - 1e-9) * size
    )
    bottom = (
        anchor[1] + math.floor((corners[:, 1].min() - anchor[1]) / size + 1e-9) * size
    )
    top = anchor[1] + math.ceil((corners[:, 1].max() - anchor[1]) / size - 1e-9) * size
    width = max(int(round((right - left) / size)), 1)
    height = max(int(round((top - bottom) / size)), 1)
    first = project.inputs[0].image
    northUp = first.transform.e < 0
    transform = (
        Affine(size, 0.0, left, 0.0, -size, top)
        if northUp
        else Affine(size, 0.0, left, 0.0, size, bottom)
    )
    return TargetGrid(transform, width, height, first.crs)


def overlapGrid(
    project: MosaicProject, referenceKey: int, movingKey: int
) -> TargetGrid | None:
    """A grid over the overlap of two inputs' footprints (their bounding
    boxes), at the finest pixel size, on the reference's pixel grid; None when
    they don't overlap."""
    reference, moving = project.input(referenceKey), project.input(movingKey)
    a, b = reference.footprint(), moving.footprint()
    left, right = max(a[:, 0].min(), b[:, 0].min()), min(a[:, 0].max(), b[:, 0].max())
    bottom, top = max(a[:, 1].min(), b[:, 1].min()), min(a[:, 1].max(), b[:, 1].max())
    size = pixelSize(project)
    anchor = a[0]
    left = anchor[0] + math.ceil((left - anchor[0]) / size - 1e-9) * size
    bottom = anchor[1] + math.ceil((bottom - anchor[1]) / size - 1e-9) * size
    width = int(math.floor((right - left) / size + 1e-9))
    height = int(math.floor((top - bottom) / size + 1e-9))
    if width < 1 or height < 1:
        return None
    northUp = reference.image.transform.e < 0
    transform = (
        Affine(size, 0.0, left, 0.0, -size, bottom + height * size)
        if northUp
        else Affine(size, 0.0, left, 0.0, size, bottom)
    )
    return TargetGrid(transform, width, height, reference.image.crs)
