"""
RasterioDataSource: default DataSource implementation for any GDAL-supported format.

Opens the file with rasterio and keeps the handle for on-demand reads.
All data methods transpose from rasterio's native (bands, h, w) to (h, w, bands).
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np

import rasterio as rio
from rasterio.windows import Window
from affine import Affine
import affine as affine_module
from pyproj import CRS

from .data_source import DataSource
from .registry import register_data_source

if TYPE_CHECKING:
    import numpy.typing as npt

# disable verbose rasterio logging
logging.getLogger("rasterio").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@register_data_source("TIFF/GeoTIFF", (".tif", ".tiff", ".geotiff", ".gtiff"))
@register_data_source(
    "Common Images", (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga")
)
class RasterioDataSource(DataSource):
    """DataSource backed by a rasterio-opened file handle.

    Works with any format GDAL supports: GeoTIFF, ENVI, PNG, JPEG, BMP, HDF5, etc.
    """

    def __init__(self, filePath: str):
        self._filePath = filePath
        self._src: rio.DatasetReader = rio.open(filePath)

    # --- Data access ---

    def getBands(self, bandIndices: npt.ArrayLike) -> np.ndarray:
        return self.getData(bandIndices=bandIndices)

    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError(
                f"Pixel ({x}, {y}) out of bounds for image of size ({self.width}, {self.height})"
            )
        window = (y, x, 1, 1)
        data = self.getData(window=window)
        # (bands, 1, 1) -> (bands,)
        result = data.squeeze()
        return result

    def getData(
        self,
        bandIndices: npt.ArrayLike | None = None,
        window: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        # process window and band inputs into rasterio formats
        rio_window = None
        if window is not None:
            row_off, col_off, height, width = window
            rio_window = Window(
                col_off=col_off, row_off=row_off, width=width, height=height
            )
        rio_indices = None
        if bandIndices is not None:
            bandIndices = np.asarray(bandIndices, dtype=np.uint)
            # rasterio uses 1-based band indexing
            rio_indices = [int(i) + 1 for i in bandIndices]

        # get data
        data = self._src.read(indexes=rio_indices, window=rio_window, masked=True)

        # (bands, h, w) -> (h, w, bands)
        data = np.moveaxis(data, 0, -1)

        # replace nodata values with NaN (we may want this to be optional in the future?)
        if np.ma.isMaskedArray(data):
            data = data.filled(np.nan)

        return data

    def readAllBands(self) -> np.ndarray:
        window = (0, 0, self.height, self.width)
        data = self.getData(window=window)
        return data

    def __getitem__(self, key) -> np.ndarray:
        if not isinstance(key, tuple):
            key = (key,)

        # Pad with full slices for missing dimensions
        while len(key) < 3:
            key = key + (slice(None),)

        row_key, col_key, band_key = key

        # Resolve band indices
        band_indices = self._resolve_slice(band_key, self.bandCount)

        # Resolve spatial window
        row_indices = self._resolve_slice(row_key, self.height)
        col_indices = self._resolve_slice(col_key, self.width)

        row_start = row_indices[0] if len(row_indices) > 0 else 0
        row_stop = row_indices[-1] + 1 if len(row_indices) > 0 else 0
        col_start = col_indices[0] if len(col_indices) > 0 else 0
        col_stop = col_indices[-1] + 1 if len(col_indices) > 0 else 0

        window = (row_start, col_start, row_stop - row_start, col_stop - col_start)
        data = self.getData(bandIndices=band_indices, window=window)

        # Handle step if slices had steps > 1
        row_step = row_key.step if isinstance(row_key, slice) and row_key.step else 1
        col_step = col_key.step if isinstance(col_key, slice) and col_key.step else 1
        if row_step != 1 or col_step != 1:
            data = data[::row_step, ::col_step, :]

        return data

    @staticmethod
    def _resolve_slice(key, length: int) -> np.ndarray:
        if isinstance(key, (int, np.integer)):
            return np.array([int(key)])
        elif isinstance(key, slice):
            return np.arange(*key.indices(length))
        elif isinstance(key, (list, np.ndarray)):
            return np.asarray(key)
        else:
            raise TypeError(f"Unsupported index type: {type(key)}")

    # --- File-intrinsic properties ---

    @property
    def filePath(self) -> str:
        return self._filePath

    @property
    def width(self) -> int:
        return self._src.width

    @property
    def height(self) -> int:
        return self._src.height

    @property
    def bandCount(self) -> int:
        return self._src.count

    @property
    def dtype(self) -> np.dtype:
        return np.dtype(self._src.dtypes[0])

    @property
    def nodata(self) -> float | None:
        return self._src.nodata

    @cached_property
    def wavelengths(self) -> np.ndarray:
        tags = self._src.tags()
        if "wavelength" in tags:
            try:
                wl_strings = [w.strip() for w in tags["wavelength"].split(",")]
                return np.array([float(w) for w in wl_strings])
            except ValueError:
                return np.array(wl_strings, dtype="U50")
        return np.arange(self.bandCount)

    @cached_property
    def wavelengthsType(self) -> type:
        wl = self.wavelengths
        if wl.dtype.kind == "f":
            return float
        elif wl.dtype.kind == "i":
            return int
        return str

    @cached_property
    def wavelengthUnits(self) -> str:
        tags = self._src.tags()
        return tags.get("wavelength_units", "Unknown")

    @cached_property
    def bandNames(self) -> list[str]:
        names = []
        for i in range(1, self.bandCount + 1):
            name = self._src.tags(i).get("name", f"Band {i}")
            names.append(name)
        return names

    @property
    def transform(self) -> Affine:
        t = self._src.transform
        if t is None:
            return affine_module.identity
        return t

    @property
    def crs(self) -> CRS | None:
        src_crs = self._src.crs
        if src_crs is None:
            return None
        try:
            return CRS.from_wkt(src_crs.to_wkt())
        except Exception:
            logger.error(
                f"Failed to parse CRS from source: {src_crs} from file {self.filePath}"
            )
            return None

    @property
    def driver(self) -> str:
        return self._src.driver

    @cached_property
    def defaultBands(self) -> np.ndarray:
        if self.bandCount >= 3:
            return np.array([0, 1, 2], dtype=np.uint)
        return np.array([0, 0, 0], dtype=np.uint)

    @cached_property
    def isParameterImage(self) -> bool:
        return False

    @cached_property
    def extraMetadata(self) -> dict:
        return {}

    @cached_property
    def description(self) -> str:
        return ""

    # --- Coordinate transformation ---

    def pixelToGeo(self, col: int, row: int) -> tuple[float, float]:
        return self._src.xy(row, col)

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        row, col = self._src.index(x, y)
        return int(col), int(row)

    # --- Lifecycle ---

    def close(self) -> None:
        if self._src is not None and not self._src.closed:
            self._src.close()

    def __del__(self):
        self.close()

    def __repr__(self) -> str:
        return f"RasterioDataSource({self._filePath!r}, {self.width}x{self.height}x{self.bandCount})"
