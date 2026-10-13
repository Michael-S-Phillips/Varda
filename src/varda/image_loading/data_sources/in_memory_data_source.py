"""
InMemoryDataSource: thin wrapper that caches raster data in memory.

Wraps another DataSource, reading all raster data into memory for fast access
while delegating metadata and coordinate transforms to the wrapped source.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

from .data_source import DataSource
from .delegating_data_source import DelegatingDataSource

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


class InMemoryDataSource(DelegatingDataSource):
    """
    DataSource that wraps another DataSource, immediately caching all of the raster data in memory.
    This allows for quick data access at the cost of higher memory usage.
    """

    def __init__(self, source: DataSource):
        super().__init__(source)
        self._data = source.readAllBands()

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

    # --- Metadata properties (shape from the data held; the rest delegated) ---

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

    # --- Lifecycle ---

    def close(self) -> None:
        self._source.close()  # the file stays open for metadata until now

    def __repr__(self) -> str:
        return f"InMemoryDataSource({self.width}x{self.height}x{self.bandCount}, dtype={self.dtype})"
