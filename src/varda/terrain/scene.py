"""The 3D terrain page's data. No Qt.

A DEM becomes a grid of heights (decimated to fit the GPU, quantized to 16
bits with 0 for no data) spanning its ground size in meters, plus a drape
image. ``pageHtml`` builds the viewer page around them: one self-contained
HTML file (three.js inlined through an import map of data URLs), which Varda
shows and which is also the web export.
"""

from __future__ import annotations

import base64
import io
import json
import math
import warnings
from collections.abc import Sequence
from pathlib import Path

import attrs
import numpy as np
from attrs import asdict, define, frozen
from scipy import ndimage
from PIL import Image
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.terrain.vectors import PageLine
from varda.utilities.resources import resource_path

MAX_SIDE = 1024  # vertices on a side, by default: about 2 million triangles
MAX_TEXTURE = 8192  # px on a side for the drape
LEVELS = 65534  # height levels (16 bits, 0 meaning no data)
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


def buildTerrain(
    dem: VardaRaster,
    band: int = 0,
    maxSide: int = MAX_SIDE,
    size: tuple[float, float] | None = None,
    fill: bool = True,
) -> Terrain:
    """``dem``'s ``band`` as a terrain grid at most ``maxSide`` vertices on a
    side. ``size`` is its ``groundSize``: pass it when building on a worker
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
    return Terrain(heights, widthM, heightM, step, filled)


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
