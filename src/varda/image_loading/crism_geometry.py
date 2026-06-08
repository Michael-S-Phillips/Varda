"""Isolated CRISM geometry (DDR backplane) support for column-locked ROI placement.

CRISM reflectance products ship a separate geometry "DDR" file whose bands give,
per pixel, the detector column ("IR Sample") and the source strip identity
("Target ID" + "Segment ID"). This module resolves that companion file and
computes the horizontal shift needed to place a copied ROI on the same detector
column as its template. It is deliberately CRISM-specific and self-contained: no
general multi-instrument abstraction until a second instrument needs one.
"""

from __future__ import annotations

import logging
import os
import re

import attrs
import numpy as np

logger = logging.getLogger(__name__)


@attrs.define
class ColumnGeometry:
    """Per-pixel CRISM geometry arrays, all shape (height, width).

    ``ir_sample`` is the detector column index; ``target_id`` and ``segment_id``
    identify the source observation strip. Missing values are NaN.
    """

    ir_sample: np.ndarray
    target_id: np.ndarray | None = None
    segment_id: np.ndarray | None = None


def _modeUnderMask(arr: np.ndarray | None, mask: np.ndarray) -> int | None:
    """Most common (non-NaN) integer value of ``arr`` under a boolean mask."""
    if arr is None:
        return None
    vals = arr[mask]
    vals = vals[~np.isnan(vals)]
    if vals.size == 0:
        return None
    uniq, counts = np.unique(vals.astype(np.int64), return_counts=True)
    return int(uniq[int(np.argmax(counts))])


def computeColumnLockedTranslation(
    templatePolygonPixels: np.ndarray,
    clickRow: int,
    clickCol: int,
    geometry: ColumnGeometry,
) -> tuple[float, float] | None:
    """Compute the (dx, dy) pixel shift for a column-locked template paste.

    ``templatePolygonPixels`` is an (N, 2) array of (col, row) pixel coordinates.
    ``clickCol`` is intentionally ignored: the horizontal placement is determined
    by the detector-column match, not the clicked column.
    Returns (dx, dy) so that the template, shifted by it, sits on the same
    detector column within the same strip at the clicked row. Returns None if
    the lock cannot be satisfied (destination row out of bounds, the template's
    strip does not reach the destination row, or no geometry under the template).
    """
    import rasterio.features
    from shapely.geometry import Polygon
    from shapely.geometry import mapping as shapely_mapping

    ir = geometry.ir_sample
    nrows, ncols = ir.shape

    # Rasterize the template polygon footprint to a boolean mask. (Same approach
    # as ROICollection.getMask, so no extra dependency is needed.)
    poly = Polygon([(float(c), float(r)) for c, r in templatePolygonPixels])
    maskBool = rasterio.features.rasterize(
        [(shapely_mapping(poly), 1)],
        out_shape=(nrows, ncols),
        fill=0,
        dtype=np.uint8,
    ).astype(bool)

    srcIr = ir[maskBool]
    srcIr = srcIr[~np.isnan(srcIr)]
    if srcIr.size == 0:
        return None
    srcIrMean = float(np.mean(srcIr))
    srcTarget = _modeUnderMask(geometry.target_id, maskBool)
    srcSeg = _modeUnderMask(geometry.segment_id, maskBool)

    destY = int(clickRow)
    if not (0 <= destY < nrows):
        return None

    rowIr = ir[destY, :]
    valid = ~np.isnan(rowIr)
    if srcTarget is not None and geometry.target_id is not None:
        valid &= geometry.target_id[destY, :] == srcTarget
    if srcSeg is not None and geometry.segment_id is not None:
        valid &= geometry.segment_id[destY, :] == srcSeg
    validXs = np.where(valid)[0]
    if validXs.size == 0:
        return None

    bestX = int(validXs[int(np.argmin(np.abs(rowIr[validXs] - srcIrMean)))])

    srcCx = float(templatePolygonPixels[:, 0].mean())
    srcCy = float(templatePolygonPixels[:, 1].mean())
    dx = bestX - srcCx
    dy = float(clickRow) - srcCy
    return (dx, dy)

# (pattern, replacement) applied to the filename stem to find the DDR companion.
_GEOMETRY_NAME_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"_mrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_mrrde_"),
    (re.compile(r"_vrr(al|if|ir|sr|su|ra)_", re.IGNORECASE), "_vrrde_"),
    (re.compile(r"_(if|sr|su)(\d{3}[a-z])", re.IGNORECASE), r"_in\2"),
]


def resolveGeometryFile(sourceFilename: str) -> str | None:
    """Map a CRISM source ``.img``/``.hdr`` path to its geometry companion path.

    Returns the companion ``.img`` path if it exists on disk, else None.
    """
    directory = os.path.dirname(sourceFilename)
    filename = os.path.basename(sourceFilename)
    stem, _ext = os.path.splitext(filename)

    for pattern, replacement in _GEOMETRY_NAME_PATTERNS:
        newStem, nSubs = pattern.subn(replacement, stem)
        if nSubs == 0 or newStem == stem:
            continue
        candidate = os.path.join(directory, newStem + ".img")
        if os.path.exists(candidate):
            return candidate
    return None
