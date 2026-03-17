"""
InMemoryDataSource: thin wrapper that caches raster data in memory.

Wraps another DataSource, reading all raster data into memory for fast access
while delegating metadata and coordinate transforms to the wrapped source.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from affine import Affine
from pyproj import CRS

from .data_source import DataSource

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class InMemoryDataSource(DataSource):
    """
    DataSource that wraps another DataSource, immediately caching all of the raster data in memory.
    This allows for quick data access at the cost of higher memory usage.
    """

    def __init__(self, source: DataSource):
        self._data = source.readAllBands()
        self._source = source

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
        masked=True,  # TODO: make this arg do something if needed
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

    # --- Metadata properties ---

    @property
    def filePath(self) -> str | None:
        return self._source.filePath

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
        return self._source.nodata

    @property
    def wavelengths(self) -> np.ndarray:
        return self._source.wavelengths

    @property
    def wavelengthsType(self) -> type:
        return self._source.wavelengthsType

    @property
    def wavelengthUnits(self) -> str:
        return self._source.wavelengthUnits

    @property
    def bandNames(self) -> list[str]:
        return self._source.bandNames

    @property
    def transform(self) -> Affine:
        return self._source.transform

    @property
    def crs(self) -> CRS | None:
        return self._source.crs

    @property
    def driver(self) -> str:
        return self._source.driver

    @property
    def defaultBands(self) -> np.ndarray:
        return self._source.defaultBands

    @property
    def isParameterImage(self) -> bool:
        return self._source.isParameterImage

    @property
    def extraMetadata(self) -> dict:
        return self._source.extraMetadata

    @property
    def description(self) -> str:
        return self._source.description

    # --- Coordinate transformation ---

    def pixelToGeo(self, col: int, row: int) -> tuple[float, float]:
        return self._source.pixelToGeo(col, row)

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        return self._source.geoToPixel(x, y)

    # --- Lifecycle ---

    def close(self) -> None:
        pass  # Nothing to close for in-memory data

    def __repr__(self) -> str:
        return f"InMemoryDataSource({self.width}x{self.height}x{self.bandCount}, dtype={self.dtype})"
