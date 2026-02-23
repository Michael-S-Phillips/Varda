"""
DataSource Protocol: defines the interface for all data sources in Varda.

All data access methods return arrays in (height, width, bands) layout,
matching the convention used throughout the rest of the application.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

import numpy as np
from affine import Affine
from pyproj import CRS

if TYPE_CHECKING:
    import numpy.typing as npt


@runtime_checkable
class DataSource(Protocol):
    """Protocol for accessing raster image data.

    Implementations wrap a specific file format or in-memory array and provide
    a uniform interface for reading pixel data, metadata, and coordinate transforms.

    All spatial data methods return arrays in **(height, width, bands)** layout.
    """

    # --- Data access ---

    def getBands(self, bandIndices: npt.ArrayLike) -> np.ndarray:
        """Read specific bands from the data source.

        Args:
            bandIndices: Zero-based band indices to read.

        Returns:
            Array with shape (height, width, n_bands).
        """
        ...

    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray:
        """Read the full spectrum at a single pixel.

        Args:
            x: Column index.
            y: Row index.

        Returns:
            1-D array with shape (bands,).
        """
        ...

    def getData(
        self,
        bandIndices: npt.ArrayLike | None = None,
        window: tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """Read raster data with optional band and spatial subsetting.

        Args:
            bandIndices: Zero-based band indices. ``None`` reads all bands.
            window: Spatial window as (row_off, col_off, height, width).
                ``None`` reads the full extent.

        Returns:
            Array with shape (height, width, bands).
        """
        ...

    def readAllBands(self) -> np.ndarray:
        """Read the entire raster into memory.

        Returns:
            Array with shape (height, width, bands).
        """
        ...

    def __getitem__(self, key) -> np.ndarray:
        """Numpy-like indexing: ``ds[y, x, bands]``.

        Supports slicing, e.g. ``ds[10:20, 30:40, 0:3]``.
        """
        ...

    # --- File-intrinsic properties ---

    @property
    def filePath(self) -> str | None:
        """Path to the source file, or ``None`` for computed data sources."""
        ...

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    @property
    def bandCount(self) -> int: ...

    @property
    def dtype(self) -> np.dtype: ...

    @property
    def nodata(self) -> float | None: ...

    @property
    def wavelengths(self) -> np.ndarray:
        """Wavelength values for each band. May be numeric or string labels."""
        ...

    @property
    def wavelengthsType(self) -> type:
        """Type of wavelength values: ``float``, ``int``, or ``str``."""
        ...

    @property
    def wavelengthUnits(self) -> str: ...

    @property
    def bandNames(self) -> list[str]: ...

    @property
    def transform(self) -> Affine:
        """Affine transform mapping pixel coordinates to CRS coordinates."""
        ...

    @property
    def crs(self) -> CRS | None:
        """Coordinate reference system, or ``None`` if not georeferenced."""
        ...

    @property
    def driver(self) -> str:
        """Format driver name (e.g. 'ENVI', 'GTiff', 'HDF5')."""
        ...

    @property
    def defaultBands(self) -> np.ndarray:
        """Default RGB band indices for display (zero-based).

        Returns an array of 3 band indices. Implementations should read
        format-specific metadata (e.g. ENVI ``default_bands``) if available,
        falling back to ``[0, 1, 2]`` or ``[0, 0, 0]``.
        """
        ...

    @property
    def isParameterImage(self) -> bool:
        """True if bands represent named parameters rather than wavelengths."""
        ...

    @property
    def extraMetadata(self) -> dict:
        """Format-specific metadata not captured by standard properties."""
        ...

    @property
    def description(self) -> str:
        """Image description string from file metadata."""
        ...

    # --- Coordinate transformation ---

    def pixelToGeo(self, col: int, row: int) -> tuple[float, float]:
        """Convert pixel coordinates to CRS coordinates.

        Args:
            col: Column (x) index.
            row: Row (y) index.

        Returns:
            (x, y) in the data source's CRS.
        """
        ...

    def geoToPixel(self, x: float, y: float) -> tuple[int, int]:
        """Convert CRS coordinates to pixel coordinates.

        Args:
            x: X coordinate in CRS.
            y: Y coordinate in CRS.

        Returns:
            (col, row) pixel indices.
        """
        ...

    # --- Lifecycle ---

    def close(self) -> None:
        """Release any underlying file handles or resources."""
        ...
