"""The 3D terrain page's data. No Qt.

A DEM becomes a grid of heights (decimated to fit the GPU, quantized to 16
bits with 0 for no data) over its ground size in meters, each point at the
center of the block of DEM pixels it averages, plus a drape image. Heights
stay in the DEM's own unit (``TerrainSettings.heightUnit``), which the viewer
and the STL export convert to meters. ``pageHtml`` builds the viewer page around them: one self-contained
HTML file (three.js inlined through an import map of data URLs), which Varda
shows and which is also the web export.
"""

from __future__ import annotations

import base64
import io
import json
import math
import sys
import warnings
from collections.abc import Sequence
from pathlib import Path

import attrs
import numpy as np
from attrs import asdict, define, frozen
from numba import njit
from scipy import ndimage
from PIL import Image
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.terrain.solid import blockCenters
from varda.terrain.vectors import PageLine
from varda.utilities.resources import resource_path

_CACHE = not getattr(sys, "frozen", False)  # see stretch_algorithms._CACHE
MAX_SIDE = 1024  # vertices on a side, by default: about 2 million triangles
MAX_TEXTURE = 8192  # px on a side for the drape
LEVELS = 65534  # height levels (16 bits, 0 meaning no data)
# Height units the 3D view knows, in meters (as the viewer's HEIGHT_UNITS)
HEIGHT_UNITS = {"m": 1.0, "km": 1000.0, "ft": 0.3048}
MAP_UNITS = {  # PROJ's unit names, as labels
    "metre": "m",
    "meter": "m",
    "kilometre": "km",
    "kilometer": "km",
    "foot": "ft",
    "US survey foot": "US ft",
}
THREE_FILES = {
    "three": "three.module.min.js",
    "three/addons/controls/OrbitControls.js": "OrbitControls.js",
}


@frozen
class Terrain:
    heights: np.ndarray  # (rows, cols) float32, NaN for no data, north row first
    widthM: float  # ground size of the grid, west to east
    heightM: float  # and south to north
    step: int  # DEM pixels per grid cell
    filled: int = 0  # grid points of gaps inside the data that were filled
    demShape: tuple[int, int] = (0, 0)  # the DEM's rows and columns (0: step × grid)

    @property
    def columns(self) -> np.ndarray:
        """Where each grid column stands: the center of the DEM pixels it
        averages, as a fraction of the extent from the west edge."""
        count = self.heights.shape[1]
        return blockCenters(self.demShape[1] or count * self.step, self.step)

    @property
    def rows(self) -> np.ndarray:
        """And each grid row, as a fraction from the north edge."""
        count = self.heights.shape[0]
        return blockCenters(self.demShape[0] or count * self.step, self.step)

    @property
    def zRange(self) -> tuple[float, float]:
        finite = self.heights[np.isfinite(self.heights)]
        return (float(finite.min()), float(finite.max())) if finite.size else (0.0, 0.0)


@define
class TerrainSettings:
    exaggeration: float = 1.0
    sunAzimuth: float = 315.0  # degrees clockwise from north
    sunElevation: float = 35.0  # degrees above the horizon
    shadows: bool = True
    background: str = "#101418"
    ambient: float = 0.35
    northArrow: bool = True
    scaleBar: bool = True  # measured at the view's center
    colorBar: bool = True  # when the drape is colored by elevation
    sides: bool = False  # a block diagram: walls down to a base
    baseDepth: float = (
        0.0  # below the lowest point (height units; 0: a quarter of the relief)
    )
    sideColor: str = "#a08e78"
    # the outline: "smooth" (cut diagonally), "stepped" (cell by cell) or
    # "rectangle" (trimmed to the largest rectangle with data everywhere)
    edges: str = "smooth"
    # the unit of the DEM's heights (a HEIGHT_UNITS key); ground sizes are meters
    heightUnit: str = "m"

    @property
    def metersPerHeightUnit(self) -> float:
        return HEIGHT_UNITS.get(self.heightUnit, 1.0)

    def toDict(self) -> dict:
        return asdict(self)

    @classmethod
    def fromDict(cls, values: dict) -> TerrainSettings:
        names = attrs.fields_dict(cls)
        return cls(**{k: v for k, v in values.items() if k in names})


def _blockMean(data: np.ndarray, step: int) -> np.ndarray:
    """``data`` averaged over step × step blocks, ignoring NaN."""
    if step <= 1:
        return data
    rows, cols = data.shape
    padded = np.full(
        (math.ceil(rows / step) * step, math.ceil(cols / step) * step),
        np.nan,
        data.dtype,
    )
    padded[:rows, :cols] = data
    blocks = padded.reshape(
        padded.shape[0] // step, step, padded.shape[1] // step, step
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN blocks
        return np.nanmean(blocks, axis=(1, 3)).astype(np.float32)


def groundSize(image: VardaRaster) -> tuple[float, float]:
    """The image's (width, height) on the ground in meters; its size in
    pixels when it has no georeferencing."""
    if not image.hasGeospatialData:
        return float(image.width), float(image.height)
    transform = image.transform
    width = abs(transform.a) * image.width
    height = abs(transform.e) * image.height
    crs = CRS.from_user_input(image.crs)
    if crs.is_geographic:
        radius = crs.ellipsoid.semi_major_metre if crs.ellipsoid else 6_371_008.8
        north = transform.f
        latitude = math.radians(north - height / 2)
        metersPerDegree = math.pi * radius / 180
        return width * metersPerDegree * math.cos(latitude), height * metersPerDegree
    factor = crs.axis_info[0].unit_conversion_factor if crs.axis_info else 1.0
    return width * factor, height * factor


def verticalUnit(crs: CRS) -> str | None:
    """The height unit (a ``HEIGHT_UNITS`` key) a CRS declares on its up
    axis (a compound CRS's vertical part, or a 3D CRS), if it's one Varda
    knows; US survey feet count as feet (2 parts per million apart)."""
    for axis in crs.axis_info:
        if axis.direction.lower() == "up":
            factor = axis.unit_conversion_factor
            for unit, meters in HEIGHT_UNITS.items():
                if math.isclose(factor, meters, rel_tol=1e-5):
                    return unit
    return None


def mapUnit(crs: CRS) -> str:
    """The unit of a CRS's map coordinates, as a short label: ° for a
    geographic CRS, m, km, ft or US ft for a projected one (otherwise PROJ's
    name for it)."""
    if crs.is_geographic:
        return "°"
    name = crs.axis_info[0].unit_name if crs.axis_info else ""
    return MAP_UNITS.get(name, name or "map units")


def fillGaps(heights: np.ndarray, smoothing: int = 4) -> tuple[np.ndarray, int]:
    """Gaps of no data enclosed by data (a DTM's voids on steep slopes, say)
    filled from the nearest heights and smoothed; no data around the outside
    stays. Returns the heights and how many points were filled."""
    valid = np.isfinite(heights)
    gaps = ndimage.binary_fill_holes(valid) & ~valid
    count = int(gaps.sum())
    if not count:
        return heights, 0
    nearest = ndimage.distance_transform_edt(
        ~valid, return_distances=False, return_indices=True
    )
    filled = heights.copy()
    filled[gaps] = heights[tuple(index[gaps] for index in nearest)]
    for _ in range(smoothing):  # soften the nearest-value terraces
        mean = ndimage.uniform_filter(np.where(np.isfinite(filled), filled, 0), 3)
        filled[gaps] = mean[gaps] / np.maximum(
            ndimage.uniform_filter(np.isfinite(filled).astype(float), 3)[gaps], 1e-9
        )
    return filled.astype(heights.dtype), count


@njit(cache=_CACHE)
def _largestRectangle(valid: np.ndarray) -> tuple[int, int, int, int]:
    """(top, left, bottom, right), exclusive, of the largest all-True
    rectangle: each row's run lengths upward as a histogram, whose largest
    rectangle a stack finds."""
    rows, cols = valid.shape
    runs = np.zeros(cols + 1, np.int64)  # a 0 at the end empties the stack
    stack = np.zeros(cols + 1, np.int64)
    best, box = 0, (0, 0, 0, 0)
    for r in range(rows):
        for c in range(cols):
            runs[c] = runs[c] + 1 if valid[r, c] else 0
        size = 0
        for c in range(cols + 1):
            while size > 0 and runs[stack[size - 1]] >= runs[c]:
                tall = runs[stack[size - 1]]
                size -= 1
                left = stack[size - 1] + 1 if size > 0 else 0
                if tall * (c - left) > best:
                    best = tall * (c - left)
                    box = (r + 1 - tall, left, r + 1, c)
            stack[size] = c
            size += 1
    return box


def trimToRectangle(heights: np.ndarray) -> np.ndarray:
    """Heights outside the largest rectangle that has data everywhere set
    to NaN, for a block with straight sides."""
    top, left, bottom, right = _largestRectangle(np.isfinite(heights))
    trimmed = np.full_like(heights, np.nan)
    trimmed[top:bottom, left:right] = heights[top:bottom, left:right]
    return trimmed


def buildTerrain(
    dem: VardaRaster,
    band: int = 0,
    maxSide: int = MAX_SIDE,
    size: tuple[float, float] | None = None,
    fill: bool = True,
    trim: bool = False,
) -> Terrain:
    """``dem``'s ``band`` as a terrain grid at most ``maxSide`` vertices on a
    side, its gaps filled (``fill``) and trimmed to a rectangle (``trim``).
    ``size`` is its ``groundSize``: pass it when building on a worker
    thread, as pyproj's CRS objects mustn't be shared between threads."""
    raw = dem.getBands([band])
    data = np.ma.filled(raw, np.nan) if np.ma.isMaskedArray(raw) else raw
    data = np.asarray(data, dtype=np.float32)[:, :, 0]
    nodata = dem.nodata
    if nodata is not None and np.isfinite(nodata):
        data = np.where(data == nodata, np.nan, data)
    step = max(1, math.ceil(max(data.shape) / maxSide))
    widthM, heightM = size if size is not None else groundSize(dem)
    heights = _blockMean(data, step)
    filled = 0
    if fill:
        heights, filled = fillGaps(heights)
    if trim:
        heights = trimToRectangle(heights)
    return Terrain(heights, widthM, heightM, step, filled, data.shape)


def quantize(heights: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Heights as uint16 (0 for no data, 1..65535 for the range) with the
    height of level 1 and the step between levels."""
    finite = np.isfinite(heights)
    if not finite.any():
        return np.zeros(heights.shape, np.uint16), 0.0, 1.0
    low, high = float(heights[finite].min()), float(heights[finite].max())
    zStep = (high - low) / LEVELS or 1.0
    levels = np.zeros(heights.shape, np.uint16)
    levels[finite] = np.round((heights[finite] - low) / zStep).astype(np.uint32) + 1
    return levels, low, zStep


def pngDataUrl(rgba: np.ndarray, maxSide: int = MAX_TEXTURE) -> str:
    """An RGBA image as a PNG data URL, shrunk to ``maxSide`` if larger."""
    image = Image.fromarray(np.ascontiguousarray(rgba, dtype=np.uint8), "RGBA")
    if max(image.size) > maxSide:
        image.thumbnail((maxSide, maxSide), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False, compress_level=6)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _dataUrl(path: Path, mime: str = "text/javascript") -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


PANEL = """<div id="panel">
<h1>{title}</h1>
<label>Exaggeration</label><input type="range" min="1" max="20" step="0.5" data-setting="exaggeration">
<label>Sun azimuth</label><input type="range" min="0" max="360" step="1" data-setting="sunAzimuth">
<label>Sun elevation</label><input type="range" min="2" max="90" step="1" data-setting="sunElevation">
<label>Shadows</label><input type="checkbox" data-setting="shadows">
<button id="home">Reset view</button>
</div>
<div id="credit">Made with <a href="https://github.com/varda-pro/Varda">Varda</a></div>"""


@frozen
class Legend:
    """A color bar: the color map's colors, low to high, and its range."""

    colors: tuple[str, ...]  # "#rrggbb"
    low: float
    high: float
    label: str = "Elevation (m)"


@frozen
class PageOverlay:
    """An image draped over part of the DEM: a PNG data URL and its bounds as
    fractions of the DEM's extent (west, south, east, north)."""

    name: str
    texture: str
    uvBounds: tuple[float, float, float, float]
    opacity: float = 1.0
    visible: bool = True


def pageHtml(
    terrain: Terrain,
    texture: str | None,
    settings: TerrainSettings,
    camera: dict | None = None,
    title: str = "Varda 3D view",
    panel: bool = False,
    overlays: Sequence[PageOverlay] = (),
    legend: Legend | None = None,
    lines: Sequence[PageLine] = (),
) -> str:
    """The viewer page: self-contained, so the same file works in Varda and
    in any browser. ``texture`` is a data URL (``pngDataUrl``) draped over
    the whole DEM, ``overlays`` over parts of it; ``panel`` adds controls for
    readers of an exported page."""
    folder = Path(resource_path("resources/terrain"))
    levels, zMin, zStep = quantize(terrain.heights)
    rows, cols = levels.shape
    data = {
        "cols": cols,
        "rows": rows,
        "widthM": terrain.widthM,
        "heightM": terrain.heightM,
        # where the grid's points stand, as fractions of the extent
        "columnAt": terrain.columns.tolist(),
        "rowAt": terrain.rows.tolist(),
        "zMin": zMin,
        "zStep": zStep,
        "heights": base64.b64encode(levels.astype("<u2").tobytes()).decode(),
        "texture": texture,
        "settings": settings.toDict(),
        "camera": camera,
        "overlays": [asdict(overlay) for overlay in overlays],
        "legend": None if legend is None else asdict(legend),
        "lines": [asdict(line) for line in lines],
    }
    importmap = {"imports": {k: _dataUrl(folder / f) for k, f in THREE_FILES.items()}}
    safeTitle = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    template = (folder / "viewer.html").read_text()
    return (
        template.replace("{{TITLE}}", safeTitle)
        .replace("{{IMPORTMAP}}", json.dumps(importmap))
        .replace("{{PANEL}}", PANEL.format(title=safeTitle) if panel else "")
        # </script> can't appear inside the inline script
        .replace("{{SCENE}}", json.dumps(data).replace("</", "<\\/"))
        .replace("{{VIEWER}}", (folder / "viewer.js").read_text())
    )
