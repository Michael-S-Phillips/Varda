"""
ArrayDataSource: DataSource backed by a raw numpy array.

Provides the full DataSource interface with sensible defaults for metadata.
Useful for tests, debug utilities, and computed/synthetic raster data.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np
from affine import Affine
import affine as affine_module
from pyproj import CRS

from .data_source import DataSource

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class ArrayDataSource(DataSource):
    """DataSource backed by a numpy array with optional metadata overrides.
    Primarily useful for debug tools and tests.

    The array must be in (height, width, bands) layout (or 2D for single-band).
    All metadata has sensible defaults so only the array is required.
    """

    def __init__(
        self,
        data: np.ndarray,
        *,
        filePath: str | None = None,
        wavelengths: np.ndarray | None = None,
        wavelengthUnits: str = "Unknown",
        bandNames: list[str] | None = None,
        transform: Affine | None = None,
        crs: CRS | None = None,
        driver: str = "Array",
        nodata: float | None = None,
        defaultBands: np.ndarray | None = None,
        isParameterImage: bool = False,
        extraMetadata: dict | None = None,
        description: str = "",
    ):
        if data.ndim == 2:
            data = data[:, :, np.newaxis]
        if data.ndim != 3:
            raise ValueError(f"Expected 2D or 3D array, got {data.ndim}D")

        self._data = data
        self._filePath = filePath
        self._wavelengths = (
            wavelengths if wavelengths is not None else np.arange(data.shape[2])
        )
        self._wavelengthUnits = wavelengthUnits
        self._bandNames = (
            bandNames
            if bandNames is not None
            else [f"Band {i + 1}" for i in range(data.shape[2])]
        )
        self._transform = transform if transform is not None else affine_module.identity
        self._crs = crs
        self._driver = driver
        self._nodata = nodata
        self._isParameterImage = isParameterImage
        self._extraMetadata = extraMetadata if extraMetadata is not None else {}
        self._description = description

        if defaultBands is not None:
            self._defaultBands = defaultBands
        elif data.shape[2] >= 3:
            self._defaultBands = np.array([0, 1, 2], dtype=np.uint)
        else:
            self._defaultBands = np.array([0, 0, 0], dtype=np.uint)

    # --- Data access ---

    def getBands(self, bandIndices: npt.ArrayLike) -> np.ndarray:
        return self.getData(bandIndices=bandIndices)

    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError(
                f"Pixel ({x}, {y}) out of bounds for image ({self.width}, {self.height})"
            )
        return self._data[y, x, :]

    def getData(
        self,
        bandIndices: npt.ArrayLike | None = None,
        window: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        data = self._data
        if window is not None:
            row_off, col_off, h, w = window
            data = data[row_off : row_off + h, col_off : col_off + w, :]
        if bandIndices is not None:
            indices = list(np.asarray(bandIndices, dtype=np.uint))
            data = data[:, :, indices]
        return data

    def readAllBands(self) -> np.ndarray:
        return self._data

    def __getitem__(self, key) -> np.ndarray:
        return self._data[key]

    # --- File-intrinsic properties ---

    @property
    def filePath(self) -> str | None:
        return self._filePath

    @property
    def width(self) -> int:
        return self._data.shape[1]

    @property
    def height(self) -> int:
        return self._data.shape[0]

    @property
    def bandCount(self) -> int:
        return self._data.shape[2]

    @property
    def dtype(self) -> np.dtype:
        return self._data.dtype

    @property
    def nodata(self) -> float | None:
        return self._nodata

    @property
    def wavelengths(self) -> np.ndarray:
        return self._wavelengths

    @cached_property
    def wavelengthsType(self) -> type:
        if self._wavelengths.dtype.kind == "f":
            return float
        elif self._wavelengths.dtype.kind == "i":
            return int
        return str

    @property
    def wavelengthUnits(self) -> str:
        return self._wavelengthUnits

    @property
    def bandNames(self) -> list[str]:
        return self._bandNames

    @property
    def transform(self) -> Affine:
        return self._transform

    @property
    def crs(self) -> CRS | None:
        return self._crs

    @property
    def driver(self) -> str:
        return self._driver

    @property
    def defaultBands(self) -> np.ndarray:
        return self._defaultBands

    @property
    def isParameterImage(self) -> bool:
        return self._isParameterImage

    @property
    def extraMetadata(self) -> dict:
        return self._extraMetadata

    @property
    def description(self) -> str:
        return self._description

    # --- Coordinate transformation ---

    def pixelToGeo(self, col: int, row: int) -> tuple[float, float]:
        x, y = self._transform * (col, row)
        return x, y

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        inv = ~self._transform
        col, row = inv * (x, y)
        return int(col), int(row)

    # --- Lifecycle ---

    def close(self) -> None:
        pass

    def __repr__(self) -> str:
        return f"ArrayDataSource({self.width}x{self.height}x{self.bandCount}, dtype={self.dtype})"
