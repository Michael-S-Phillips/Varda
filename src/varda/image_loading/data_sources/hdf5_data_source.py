"""
HDF5DataSource: DataSource for HDF5 files using h5py.

Used as a fallback when rasterio/GDAL cannot open an HDF5 file.
Preserves the BFS dataset discovery logic from the original HDF5ImageLoader.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import h5py
import numpy as np
from affine import Affine
import affine as affine_module
from pyproj import CRS

from .data_source import DataSource
from .registry import register_data_source

if TYPE_CHECKING:
    import numpy.typing as npt

logger = logging.getLogger(__name__)


@register_data_source("HDF5", (".h5", ".hdf5"))
class HDF5DataSource(DataSource):
    """DataSource for HDF5 files that rasterio/GDAL cannot handle.

    Uses h5py to open the file. Discovers the main raster dataset via
    known paths or BFS traversal. Data is always returned in (h, w, bands) layout.

    DOES NOT support geospatial metadata or coordinate transformations yet.
    """

    def __init__(self, filePath: str):
        self._filePath = filePath
        self._hdf = h5py.File(filePath, "r")
        self._dataset: h5py.Dataset = self._findDataset()
        if self._dataset is None:
            self._hdf.close()
            raise ValueError(f"Could not find a suitable raster dataset in {filePath}")
        self._ensureLayout()

    def _findDataset(self) -> h5py.Dataset | None:
        """Find the main raster dataset in the HDF5 file."""
        # Strategy 1: known paths
        knownPaths = [
            "SERC/Reflectance/Reflectance_Data",
            "Reflectance/Reflectance_Data",
            "Reflectance_Data",
            "Data/Reflectance",
            "Data",
        ]
        for path in knownPaths:
            try:
                ds = self._hdf[path]
                if isinstance(ds, h5py.Dataset):
                    logger.info(f"Found dataset at known path: {path}")
                    return ds
            except (KeyError, AttributeError):
                pass

        # Strategy 2: BFS for a 2D+ dataset
        visited: set[int] = set()
        queue = [self._hdf]
        while queue:
            current = queue.pop(0)
            if id(current) in visited:
                continue
            visited.add(id(current))

            if isinstance(current, h5py.Dataset) and len(current.shape) >= 2:
                if len(current.shape) == 3 or (
                    len(current.shape) == 2
                    and current.shape[0] > 1
                    and current.shape[1] > 1
                ):
                    logger.info(f"Found dataset via BFS: {current.name}")
                    return current

            if isinstance(current, h5py.Group):
                for key in current:
                    queue.append(current[key])

        return None

    def _ensureLayout(self):
        """Determine if the dataset is (h, w, bands) or (bands, h, w) and record it."""
        shape = self._dataset.shape
        if len(shape) == 2:
            # Single band: (h, w) - we'll expand to (h, w, 1) on read
            self._needsTranspose = False
            self._height = shape[0]
            self._width = shape[1]
            self._bandCount = 1
        elif len(shape) == 3:
            # Heuristic: if first dim is smallest, assume (bands, h, w)
            if shape[0] < shape[1] and shape[0] < shape[2]:
                self._needsTranspose = True
                self._bandCount = shape[0]
                self._height = shape[1]
                self._width = shape[2]
            else:
                self._needsTranspose = False
                self._height = shape[0]
                self._width = shape[1]
                self._bandCount = shape[2]
        else:
            raise ValueError(f"Unsupported dataset shape: {shape}")

    def _toHWB(self, data: np.ndarray) -> np.ndarray:
        """Ensure data is in (h, w, bands) layout."""
        if data.ndim == 2:
            return data[:, :, np.newaxis]
        if self._needsTranspose:
            return np.moveaxis(data, 0, -1)
        return data

    # --- Data access ---

    def getBands(self, bandIndices: npt.ArrayLike) -> np.ndarray:
        return self.getData(bandIndices=bandIndices)

    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray:
        if x < 0 or x >= self._width or y < 0 or y >= self._height:
            raise IndexError(
                f"Pixel ({x}, {y}) out of bounds for image ({self._width}, {self._height})"
            )
        window = (y, x, 1, 1)
        data = self.getData(window=window)
        return data.squeeze()

    def getData(
        self,
        bandIndices: npt.ArrayLike | None = None,
        window: tuple[int, int, int, int] | None = None,
        masked=True,  # TODO: make this arg do something if needed
    ) -> np.ndarray:
        # process window
        if window is not None:
            row_off, col_off, h, w = window
            rSlice = slice(row_off, row_off + h)
            cSlice = slice(col_off, col_off + w)
        else:
            rSlice = slice(None)
            cSlice = slice(None)

        # process band indices
        bIdx = None
        if bandIndices is not None:
            bIdx = list(np.asarray(bandIndices, dtype=np.uint))

        # read data
        if bIdx is not None:
            if self._needsTranspose:
                data = self._dataset[bIdx, rSlice, cSlice]
            else:
                data = (
                    self._dataset[rSlice, cSlice, :][:, :, bIdx]
                    if self._bandCount > 1
                    else self._dataset[rSlice, cSlice]
                )
        else:
            if self._needsTranspose:
                data = self._dataset[:, rSlice, cSlice]
            else:
                data = (
                    self._dataset[rSlice, cSlice]
                    if self._bandCount == 1
                    else self._dataset[rSlice, cSlice, :]
                )

        return self._toHWB(np.asarray(data))

    def readAllBands(self) -> np.ndarray:
        return self.getData()

    def __getitem__(self, key) -> np.ndarray:
        if not isinstance(key, tuple):
            key = (key,)
        while len(key) < 3:
            key = key + (slice(None),)

        row_key, col_key, band_key = key

        # Read the full data then slice (h5py supports slicing too but this is simpler)
        # For large files this could be optimized to pass slices directly to h5py
        if self._needsTranspose:
            band_indices = self._resolveSlice(band_key, self._bandCount)
            row_indices = self._resolveSlice(row_key, self._height)
            col_indices = self._resolveSlice(col_key, self._width)
            rSlice = (
                slice(row_indices[0], row_indices[-1] + 1)
                if len(row_indices)
                else slice(0, 0)
            )
            cSlice = (
                slice(col_indices[0], col_indices[-1] + 1)
                if len(col_indices)
                else slice(0, 0)
            )
            data = self._dataset[list(band_indices), rSlice, cSlice]
        else:
            row_indices = self._resolveSlice(row_key, self._height)
            col_indices = self._resolveSlice(col_key, self._width)
            band_indices = self._resolveSlice(band_key, self._bandCount)
            rSlice = (
                slice(row_indices[0], row_indices[-1] + 1)
                if len(row_indices)
                else slice(0, 0)
            )
            cSlice = (
                slice(col_indices[0], col_indices[-1] + 1)
                if len(col_indices)
                else slice(0, 0)
            )
            if self._bandCount == 1:
                data = self._dataset[rSlice, cSlice]
            else:
                data = self._dataset[rSlice, cSlice, :][:, :, list(band_indices)]

        result = self._toHWB(np.asarray(data))

        # Handle step
        row_step = row_key.step if isinstance(row_key, slice) and row_key.step else 1
        col_step = col_key.step if isinstance(col_key, slice) and col_key.step else 1
        if row_step != 1 or col_step != 1:
            result = result[::row_step, ::col_step, :]
        return result

    @staticmethod
    def _resolveSlice(key, length: int) -> np.ndarray:
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
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def bandCount(self) -> int:
        return self._bandCount

    @property
    def dtype(self) -> np.dtype:
        return self._dataset.dtype

    @property
    def nodata(self) -> float | None:
        return None

    @cached_property
    def wavelengths(self) -> np.ndarray:
        wl = self._findWavelengths()
        if wl is not None and len(wl) == self._bandCount:
            return wl
        return np.arange(self._bandCount)

    def _findWavelengths(self) -> np.ndarray | None:
        """Search for wavelength data in the HDF5 hierarchy."""
        knownPaths = [
            "SERC/Reflectance/Metadata/Spectral_Data/Wavelength",
            "Reflectance/Metadata/Spectral_Data/Wavelength",
            "Metadata/Spectral_Data/Wavelength",
            "Wavelength",
        ]
        for path in knownPaths:
            try:
                wl = self._hdf[path][:]
                logger.info(f"Found wavelength data at {path}")
                if len(wl.shape) > 1:
                    wl = wl.flatten()
                return wl
            except (KeyError, AttributeError):
                pass

        # BFS search
        result = None

        def findWavelength(name, obj):
            nonlocal result
            if result is not None:
                return
            if (
                isinstance(obj, h5py.Dataset)
                and "wavelength" in name.lower()
                and len(obj.shape) <= 2
            ):
                try:
                    wl = obj[:]
                    if len(wl.shape) > 1:
                        wl = wl.flatten()
                    result = wl
                    logger.info(f"Found wavelength data at {name}")
                except Exception as e:
                    logger.debug(f"Error reading wavelength data from {name}: {e}")

        self._hdf.visititems(findWavelength)
        return result

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
        return "Unknown"

    @cached_property
    def bandNames(self) -> list[str]:
        return [f"Band {i + 1}" for i in range(self._bandCount)]

    @property
    def transform(self) -> Affine:
        return affine_module.identity

    @property
    def crs(self) -> CRS | None:
        return None

    @property
    def driver(self) -> str:
        return "HDF5"

    @cached_property
    def defaultBands(self) -> np.ndarray:
        if self._bandCount >= 3:
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
        x, y = self.transform * (col, row)
        return x, y

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        inv = ~self.transform
        col, row = inv * (x, y)
        return int(col), int(row)

    # --- Lifecycle ---

    def close(self) -> None:
        if self._hdf is not None:
            try:
                self._hdf.close()
            except Exception:
                pass

    def __del__(self):
        self.close()

    def __repr__(self) -> str:
        return f"HDF5DataSource({self._filePath!r}, {self._width}x{self._height}x{self._bandCount})"
