"""
VardaRaster: the primary entity for raster image data in Varda.

Wraps a DataSource and holds application-level metadata (name, default bands, etc.).
Replaces the old Image + Metadata pair.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

import numpy as np
import numpy.typing as npt
from affine import Affine
import affine as affine_module
from pyproj import CRS

from varda.common.entities import Spectrum
from varda.image_loading.data_sources import InMemoryDataSource

if TYPE_CHECKING:
    from varda.image_loading.data_sources.data_source import DataSource

logger = logging.getLogger(__name__)


@dataclass
class VardaRaster:
    """Primary raster image entity in Varda.

    Wraps a DataSource for data access and holds application-level metadata.
    """

    _dataSource: DataSource
    name: str = ""
    defaultBand: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=np.uint))
    extraMetadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.name and self._dataSource.filePath:
            # Derive name from file path
            self.name = self._dataSource.filePath.split("/")[-1]
        if not isinstance(self.defaultBand, np.ndarray):
            self.defaultBand = np.array(self.defaultBand, dtype=np.uint)

    # alternate constructor
    @classmethod
    def fromDataSource(cls, dataSource: DataSource) -> VardaRaster:
        """Create a VardaRaster directly from a DataSource, deriving metadata from it."""
        if dataSource.filePath is not None:
            name = Path(dataSource.filePath).name
        else:
            name = "Untitled"
        return cls(
            _dataSource=dataSource,
            name=name,
            defaultBand=dataSource.defaultBands,
            extraMetadata=dataSource.extraMetadata,
        )

    # --- High-level data access ---

    def getSpectrum(self, x: int, y: int) -> Spectrum:
        """Get the spectrum at a specific pixel location.

        Args:
            x: Column index.
            y: Row index.

        Returns:
            Spectrum with values and wavelengths.
        """
        values = self._dataSource.getPixelSpectrum(x, y)
        return Spectrum(
            values=values, wavelengths=self.wavelengths, pixel_coordinates=(x, y)
        )

    def getBands(self, bandIndices: npt.ArrayLike) -> np.ndarray:
        """Get raster data for specific bands.

        Returns:
            Array with shape (height, width, n_bands).
        """
        return self._dataSource.getBands(bandIndices)

    def getData(
        self,
        bandIndices: list[int] | None = None,
        window: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """Get raster data with optional band and spatial subsetting.

        Returns:
            Array with shape (height, width, bands).
        """
        return self._dataSource.getData(bandIndices, window)

    def __getitem__(self, key) -> np.ndarray:
        """Numpy-like indexing: ``raster[y, x, :]``."""
        return self._dataSource[key]

    # --- Coordinate transformation ---

    def pixelToGeo(self, col: int, row: int) -> tuple[float, float]:
        """Convert pixel coordinates to CRS coordinates."""
        return self._dataSource.pixelToGeo(col, row)

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        """Convert CRS coordinates to pixel coordinates."""
        return self._dataSource.geoToPixel(x, y)

    # --- Delegated properties from DataSource ---

    @property
    def width(self) -> int:
        return self._dataSource.width

    @property
    def height(self) -> int:
        return self._dataSource.height

    @property
    def bandCount(self) -> int:
        return self._dataSource.bandCount

    @property
    def dtype(self) -> np.dtype:
        return self._dataSource.dtype

    @property
    def nodata(self) -> float | None:
        return self._dataSource.nodata

    @property
    def wavelengths(self) -> np.ndarray:
        return self._dataSource.wavelengths

    @property
    def wavelengthsType(self) -> type:
        return self._dataSource.wavelengthsType

    @property
    def wavelengthUnits(self) -> str:
        return self._dataSource.wavelengthUnits

    @property
    def bandNames(self) -> list[str]:
        return self._dataSource.bandNames

    @property
    def transform(self) -> Affine:
        return self._dataSource.transform

    @property
    def crs(self) -> CRS | None:
        return self._dataSource.crs

    @property
    def filePath(self) -> str | None:
        return self._dataSource.filePath

    @property
    def driver(self) -> str:
        return self._dataSource.driver

    @property
    def hasGeospatialData(self) -> bool:
        return self.crs is not None and self.transform != affine_module.identity

    @property
    def dataSource(self) -> DataSource:
        """Access the underlying DataSource directly."""
        return self._dataSource

    # --- Memory management ---

    def loadIntoMemory(self) -> VardaRaster:
        """Return a new VardaRaster backed by an InMemoryDataSource.

        Reads all data from the current DataSource into memory.
        """

        memDs = InMemoryDataSource(self._dataSource)
        return VardaRaster(
            _dataSource=memDs,
            name=self.name,
            defaultBand=self.defaultBand.copy(),
            extraMetadata=dict(self.extraMetadata),
        )

    def close(self) -> None:
        """Close the underlying DataSource."""
        self._dataSource.close()

    # --- Compatibility layer (temporary, for migration) ---

    @cached_property
    def raster(self) -> np.ndarray:
        """Full raster data as (h, w, bands) array.

        .. deprecated::
            Use getBands(), getData(), or getSpectrum() instead.
            This loads the entire image into memory.
        """
        warnings.warn(
            "VardaRaster.raster is deprecated. Use getBands(), getData(), or getSpectrum() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._dataSource.readAllBands()

    @property
    def metadata(self) -> CompatMetadata:
        """Backward-compatible metadata adapter.

        .. deprecated::
            Access properties directly on VardaRaster instead of through .metadata.
        """
        return CompatMetadata(self)

    def __repr__(self) -> str:
        return (
            f"VardaRaster({self.name!r}, {self.width}x{self.height}x{self.bandCount})"
        )


class CompatMetadata:
    """Backward-compatible adapter that makes ``image.metadata.X`` work during migration.

    Delegates to VardaRaster properties so old code keeps working.
    """

    def __init__(self, raster: VardaRaster):
        self._raster = raster

    @property
    def filePath(self) -> str:
        return self._raster.filePath or ""

    @property
    def driver(self) -> str:
        return self._raster.driver

    @property
    def width(self) -> int:
        return self._raster.width

    @property
    def height(self) -> int:
        return self._raster.height

    @property
    def bandCount(self) -> int:
        return self._raster.bandCount

    @property
    def dtype(self) -> str:
        return str(self._raster.dtype)

    @property
    def dataIgnore(self) -> float:
        nd = self._raster.nodata
        return nd if nd is not None else 0

    @property
    def defaultBand(self) -> np.ndarray:
        return self._raster.defaultBand

    @property
    def wavelengths(self) -> np.ndarray:
        return self._raster.wavelengths

    @property
    def wavelengths_type(self) -> type:
        return self._raster.wavelengthsType

    @property
    def name(self) -> str:
        return self._raster.name

    @property
    def transform(self) -> Affine:
        return self._raster.transform

    @property
    def crs(self) -> CRS | None:
        return self._raster.crs

    @property
    def extraMetadata(self) -> dict:
        return self._raster.extraMetadata

    @property
    def hasGeospatialData(self) -> bool:
        return self._raster.hasGeospatialData

    def toFlatDict(self) -> dict:
        core = {
            "filePath": self.filePath,
            "driver": self.driver,
            "width": self.width,
            "height": self.height,
            "bandCount": self.bandCount,
            "dtype": self.dtype,
            "dataIgnore": self.dataIgnore,
            "defaultBand": self.defaultBand,
            "wavelengths": self.wavelengths,
            "name": self.name,
        }
        core.update(self._raster.extraMetadata)
        return core

    def __iter__(self):
        return iter(self.toFlatDict().items())

    def __getitem__(self, item):
        return self.toFlatDict().get(item)

    def __repr__(self):
        items = self.toFlatDict()
        out = "CompatMetadata:\n"
        for key, value in items.items():
            out += f"    {key}: {value}\n"
        return out
