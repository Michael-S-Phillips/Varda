"""Linked images: where a point or a line on one image falls on the others,
either the same pixel (products of one pipeline on one grid) or the same
place on the map (images on different grids or map projections), and what
each image holds there. No Qt.

An image without georeferencing can only be linked by pixel, so map links
fall back to the pixel for it; and linking by pixel pairs different places
on images that aren't on one grid. ``linkWarnings`` says when either
happens, for the workspace to show.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from attrs import frozen
from pyproj import CRS, Transformer

from varda.common.entities import VardaRaster
from varda.common.grid import sameGrid
from varda.common.parameter import LabeledEnum
from varda.utilities.proj_lock import PROJ_LOCK


class Link(LabeledEnum):
    PIXEL = "By pixel"
    MAP = "By map location"


def linkedPoints(
    images: Sequence[VardaRaster],
    source: int,
    points: npt.ArrayLike,
    link: Link,
) -> list[np.ndarray]:
    """``points`` (n, 2; image coordinates, x = column) on ``images[source]``
    in each image's own coordinates."""
    xy = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    origin = images[source]
    if link is Link.PIXEL or not origin.hasGeospatialData:
        return [xy.copy() for _ in images]
    mapped = origin.imageToGeo(xy)
    originCrs = CRS.from_user_input(origin.crs)
    out = []
    for image in images:
        if not image.hasGeospatialData:
            out.append(xy.copy())
            continue
        crs = CRS.from_user_input(image.crs)
        there = mapped
        if crs != originCrs:
            with PROJ_LOCK:
                transformer = Transformer.from_crs(originCrs, crs, always_xy=True)
                there = np.column_stack(transformer.transform(*mapped.T))
        out.append(image.geoToImage(there))
    return out


def _names(images: Sequence[VardaRaster]) -> str:
    return ", ".join(image.name for image in images)


def linkWarnings(images: Sequence[VardaRaster], link: Link) -> list[str]:
    """What isn't linked the way ``link`` says: images without
    georeferencing (linked by pixel, even by map location), or images not on
    the first image's grid (linked by pixel, so the same pixel is a
    different place)."""
    if link is Link.MAP:
        plain = [image for image in images if not image.hasGeospatialData]
        if not plain:
            return []
        if len(plain) == len(images):
            return ["No image has georeferencing, so they're linked by pixel."]
        return [
            f"Linked by pixel, not map location: {_names(plain)} "
            "(no georeferencing). Placing the cursor on one of them links "
            "every image by pixel."
        ]
    first = images[0]
    other = [image for image in images[1:] if not sameGrid(image, first)]
    if not other:
        return []
    return [
        f"Not on {first.name}'s grid: {_names(other)} (size or georeferencing "
        "differ). Linked by pixel, the same pixel there is a different place; "
        "link by map location instead."
    ]


@frozen
class LinkedSpectrum:
    axis: np.ndarray  # nm, or band numbers when the bands aren't wavelengths
    displayAxis: np.ndarray  # in the image's own unit, for plotting
    values: np.ndarray  # NaN for no data and bad bands
    axisLabel: str
    axisUnit: str = "band"  # displayAxis's unit (e.g. nm, µm), or "band" numbers


def spectrumAt(image: VardaRaster, x: float, y: float) -> LinkedSpectrum | None:
    """The spectrum of the pixel containing image point (``x``, ``y``), or
    None off the image."""
    col, row = int(np.floor(x)), int(np.floor(y))
    if not (0 <= col < image.width and 0 <= row < image.height):
        return None
    values = np.array(image.getSpectrum(col, row).values, dtype=np.float64)
    model = image.bandModel
    if model.noData is not None:
        values[values == model.noData] = np.nan
    if model.badBands.size == values.size:
        values[model.badBands] = np.nan
    if model.centers is None:
        bands = np.arange(1, values.size + 1, dtype=np.float64)
        return LinkedSpectrum(bands, bands, values, "Band")
    return LinkedSpectrum(
        model.centers,
        model.native(model.centers),
        values,
        f"Wavelength ({model.label})",
        model.label,
    )


def bitPlanes(values: np.ndarray, width: int) -> np.ndarray:
    """A spectrum of bit masks as (``width`` bits, bands): 1 where a bit is
    set, 0 where not, NaN for missing values (no data, bad bands)."""
    values = np.asarray(values, dtype=np.float64)
    missing = ~np.isfinite(values)
    masks = np.where(missing, 0, values).astype(np.uint64)
    planes = (
        (masks[None, :] >> np.arange(width, dtype=np.uint64)[:, None]) & 1
    ).astype(np.float64)
    planes[:, missing] = np.nan
    return planes


def highestBit(values: np.ndarray) -> int:
    """How many bits the largest finite value needs (at least 1)."""
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    largest = int(finite.max()) if finite.size else 0
    return max(largest.bit_length(), 1)
