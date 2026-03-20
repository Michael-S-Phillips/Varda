"""
entities.py: data structures used throughout Varda
"""

# standard library
from __future__ import annotations
from dataclasses import dataclass, field
import logging
import warnings
from typing import Any, Dict, Optional, TYPE_CHECKING
from datetime import datetime
import uuid
from enum import Enum
from functools import cached_property
from pathlib import Path

# third party imports
import attrs
import affine
from affine import Affine
import numpy as np
import numpy.typing as npt
import geopandas as gpd
from PyQt6.QtGui import QColor
import rasterio as rio
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from varda.image_loading.data_sources import DataSource


class VardaRaster:
    """Primary raster image entity in Varda.

    Wraps a DataSource for data access and holds application-level metadata.
    """

    def __init__(self, dataSource: DataSource, name: str | None = None):
        self._dataSource = dataSource
        self._name = name

    # alternate constructor
    @classmethod
    def fromDataSource(cls, dataSource: DataSource) -> VardaRaster:
        """Create a VardaRaster directly from a DataSource, deriving metadata from it."""
        return cls(dataSource)

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
        masked=True,
    ) -> np.ndarray:
        """Get raster data with optional band and spatial subsetting.

        Returns:
            Array with shape (height, width, bands).
        """
        return self._dataSource.getData(bandIndices, window, masked=masked)

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
    def name(self) -> str:
        if self._name is None:
            if self._dataSource.filePath is not None:
                self._name = Path(self._dataSource.filePath).name
            else:
                self._name = "Untitled"

        return self._name

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
    def defaultBands(self) -> np.ndarray:
        return self._dataSource.defaultBands

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
        return self.crs is not None and self.transform != affine.identity

    @property
    def extraMetadata(self) -> dict:
        return self._dataSource.extraMetadata

    @property
    def dataSource(self) -> DataSource:
        """Access the underlying DataSource directly."""
        return self._dataSource

    # --- Memory management ---

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
    def defaultBands(self) -> np.ndarray:
        return self._raster.defaultBands

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
            "defaultBands": self.defaultBands,
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


@attrs.frozen(slots=True)
class Spectrum:
    """data container representing a Spectrum object in Varda

    Attributes:
        values (np.ndarray): a 1d array storing the spectral values.
        wavelengths (np.ndarray): a 1d array storing the wavelengths corresponding to the spectral values.
        index: A unique identifier for the spectrum. Mainly to be used for comparisons.
    """

    values: np.ndarray = attrs.field(converter=np.asarray)
    wavelengths: np.ndarray | list[str] = attrs.field(converter=np.asarray)
    pixel_coordinates: tuple[int, int] | None = None

    @values.validator
    def _check_values(self, attribute, value):
        if value.ndim != 1:
            raise ValueError(f"values must be a 1d array, got {value.ndim}d array")


class ROIMode(Enum):
    """Enum to define different ROI drawing modes."""

    FREEHAND = 0
    RECTANGLE = 1
    ELLIPSE = 2
    POLYGON = 3


@attrs.frozen(slots=True)
class VardaROI:
    """Immutable snapshot of a single ROI feature.

    Attributes:
        fid: Feature ID, unique within an ROICollection.
        name: Display name.
        color: RGBA color.
        geometry: Shapely geometry in CRS or pixel coordinates.
        roiType: Drawing mode used to create this ROI.
        properties: Arbitrary user-defined metadata.
    """

    fid: int
    name: str
    color: QColor
    geometry: BaseGeometry
    roiType: ROIMode
    properties: dict[str, Any] = attrs.Factory(dict)


@dataclass
class Metadata:
    """Data container representing the metadata of an image.

    This ensures that every image contains a standard base set of metadata,
    but allows for adding extra metadata items via _extraMetadata.

    Note that this data container is mutable, But do not directly modify its contents.
    use ProjectContext to edit it so that the program knows when it's changed.
    """

    filePath: str = ""
    driver: str = ""
    width: int = 0
    height: int = 0
    dtype: str = ""
    dataIgnore: float = 0
    bandCount: int = 0
    defaultBand: np.ndarray[tuple[int], np.dtype[np.uint]] = field(
        default_factory=lambda: np.zeros(3, dtype=np.uint)
    )
    wavelengths: np.ndarray = field(default_factory=lambda: np.zeros(0))
    wavelengths_type: Type = float
    name: str = ""
    transform: Affine = affine.identity
    crs: CRS | None = None

    extraMetadata: Dict[str, str | int | float] = field(default_factory=dict)

    def __post_init__(self):
        """Validate that all attributes are of the correct type and handle unexpected kwargs."""
        if not isinstance(self.filePath, str):
            raise self.BadMetadataError("filePath", "str", self.filePath)
        if not isinstance(self.driver, str):
            raise self.BadMetadataError("driver", "str", self.driver)
        if not isinstance(self.width, int):
            raise self.BadMetadataError("width", "int", self.width)
        if not isinstance(self.dtype, str):
            raise self.BadMetadataError("dtype", "str", self.dtype)
        if not isinstance(self.dataIgnore, (int, float)):
            raise self.BadMetadataError("dataIgnore", "int or float", self.dataIgnore)
        if not isinstance(self.bandCount, int):
            raise self.BadMetadataError("bandCount", "int", self.bandCount)
        if not isinstance(self.defaultBand, list | np.ndarray):
            raise self.BadMetadataError("defaultBand", "Band", self.defaultBand)
        if not isinstance(self.wavelengths, np.ndarray):
            raise self.BadMetadataError("wavelengths", "np.ndarray", self.wavelengths)
        if not isinstance(self.extraMetadata, dict):
            raise self.BadMetadataError("extraMetadata", "dict", self.extraMetadata)
        for key, value in self.extraMetadata.items():
            if not self._checkExtraMetadata(value):
                raise self.BadMetadataError(
                    f"Extra Metadata: {key}", "str, int, or float", value
                )

        # fix inputs
        if self.wavelengths.size == 0:
            self.wavelengths = np.arange(self.bandCount)
        if len(self.name) == 0:
            self.name = self.filePath.split("/")[-1]

    def __init__(self, **kwargs):
        """
        Initialize metadata with flexible handling of unexpected keyword arguments.
        Any unexpected kwargs are placed in extraMetadata automatically.
        """
        # Get the list of expected field names from the dataclass
        expected_fields = [f.name for f in self.__dataclass_fields__.values()]

        # Handle expected fields
        for f in expected_fields:
            if f in kwargs:
                setattr(self, f, kwargs.pop(f))
            elif f == "extraMetadata":
                # Initialize extraMetadata if not provided
                self.extraMetadata = kwargs.pop("extraMetadata", {})

        # Move any remaining unexpected kwargs to extraMetadata
        for key, value in kwargs.items():
            logger.warning(
                f"Unexpected keyword argument '{key}' moved to extraMetadata"
            )
            self.extraMetadata[key] = value

        # I think this doesnt get called automatically if we override __init__
        self.__post_init__()

    def _checkExtraMetadata(self, item):
        """Check if a value is serializable by JSON."""
        if isinstance(item, (str, int, float)):
            return True
        if isinstance(item, (list, tuple)):
            return True and all(self._checkExtraMetadata(i) for i in item)
        if isinstance(item, dict):
            return True and all(
                self._checkExtraMetadata(key) and self._checkExtraMetadata(value)
                for key, value in item.items()
            )
        return False

    def serialize(self):
        """Generates a dictionary representation of the metadata."""
        return {
            "filePath": self.filePath,
            "driver": self.driver,
            "width": self.width,
            "height": self.height,
            "dtype": self.dtype,
            "dataIgnore": self.dataIgnore,
            "bandCount": self.bandCount,
            "defaultBand": self.defaultBand.serialize(),
            "wavelengths": self.wavelengths.tolist(),
            "extraMetadata": self.extraMetadata,
            "name": self.name,
        }

    @classmethod
    def deserialize(cls, data: Any):
        """Deserialize a dictionary representation of the metadata."""
        return cls(
            filePath=data["filePath"],
            driver=data["driver"],
            width=data["width"],
            height=data["height"],
            dtype=data["dtype"],
            dataIgnore=data["dataIgnore"],
            bandCount=data["bandCount"],
            defaultBand=data["defaultBand"],
            wavelengths=np.array(data["wavelengths"]),
            extraMetadata=data["extraMetadata"],
            name=data.get("name", ""),
        )

    # other methods
    def toFlatDict(self):
        """generate a flat dict containing all the metadata and extra metadata"""
        coreMetadata = {
            key: value for key, value in self.__dict__.items() if key != "extraMetadata"
        }
        return {**coreMetadata, **self.extraMetadata}

    @property
    def hasGeospatialData(self):
        """Check if the metadata contains geospatial data."""
        return self.crs is not None and self.transform is not None

    # magic methods to add the ability to iterate through the items
    def __iter__(self):
        items = self.toFlatDict().items()
        for attr, value in items:
            yield attr, value

    def __repr__(self):
        allItems = self.toFlatDict()
        out = "Metadata:\n"
        for key, value in allItems.items():
            out += "    " + f"{key}: {value}" + "\n"
        return out

    def __getitem__(self, item):
        return self.toFlatDict().get(item)

    class BadMetadataError(Exception):
        """Raised when the input given to metadata is of an incompatible format."""

        def __init__(self, itemName, correctType, actualValue):
            self.message = (
                f"{itemName} must be a {correctType}, got {type(actualValue).__name__}"
            )
            super().__init__(self.message)


@dataclass
class ROICustomData:
    """Stores custom data for an ROI"""

    values: Dict[str, Any] = field(default_factory=dict)

    def serialize(self):
        """Serialize custom data for storage"""
        # Convert any non-serializable values to strings
        serialized = {}
        for key, value in self.values.items():
            if isinstance(value, np.ndarray):
                serialized[key] = value.tolist()
            else:
                serialized[key] = value
        return serialized

    @classmethod
    def deserialize(cls, data):
        """Deserialize custom data from storage"""
        custom_data = cls()
        custom_data.values = data
        return custom_data


@dataclass
class ROI:
    """Enhanced data container for a region of interest in an image.

    Attributes:
        id: Unique identifier for the ROI
        name: User-friendly name for the ROI
        mode: Drawing mode for the ROI (e.g., freehand, rectangle)
        sourceImage: The source image this ROI was created from
        points: Points defining the ROI in pixel coordinates [x, y]
        geoPoints: Points in geographic coordinates (if available) [lon, lat]
        color: The ROI color in RGBA 0-255 format, in a QColor object
        visible: Whether the ROI is currently visible
        creationTime: When the ROI was created
        description: User description of the ROI
        arraySlice: Extracted image data within the ROI (optional)
        meanSpectrum: Mean spectral values within the ROI (optional)
        customData: Custom user-defined data associated with the ROI
    """

    gdf: Optional[gpd.GeoDataFrame] = field(default_factory=lambda: gpd.GeoDataFrame())
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed ROI"
    mode: ROIMode = ROIMode.FREEHAND
    sourceImage: Image = None
    points: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    geoPoints: Optional[np.ndarray] = None
    color: QColor = field(default_factory=lambda: QColor(255, 0, 0, 128))
    visible: bool = True
    creationTime: datetime = field(default_factory=datetime.now)
    description: str = "No description"
    arraySlice: Optional[np.ndarray] = None
    meanSpectrum: Optional[np.ndarray] = None
    customData: ROICustomData = field(default_factory=ROICustomData)

    def __post_init__(self):
        """Validate and initialize the ROI after creation"""
        # Ensure points is a numpy array
        if not isinstance(self.points, np.ndarray):
            if isinstance(self.points, list):
                self.points = np.array(self.points)
            else:
                logger.warning(
                    f"Converting invalid points type {type(self.points)} to empty array"
                )
                self.points = np.array([])

        # Same for geo_points
        if self.geoPoints is not None and not isinstance(self.geoPoints, np.ndarray):
            if isinstance(self.geoPoints, list):
                self.geoPoints = np.array(self.geoPoints)
            else:
                logger.warning(
                    f"Converting invalid geo_points type {type(self.geoPoints)} to None"
                )
                self.geoPoints = None

        # Ensure color is a valid RGBA tuple
        if not isinstance(self.color, QColor):
            logger.warning(f"Invalid color {self.color}, using default")
            self.color = QColor(255, 0, 0, 128)  # Default red with 50% opacity

    def updateProperties(self, **kwargs):
        """Update multiple ROI properties at once"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown ROI property: {key}")

    def getCustomValue(self, column_name, default=None):
        """Get a custom data value by column name"""
        return self.customData.values.get(column_name, default)

    def setCustomValue(self, column_name, value):
        """Set a custom data value"""
        self.customData.values[column_name] = value

    def getBounds(self):
        """Calculate the bounding box of the ROI points"""
        if len(self.points) == 0:
            return 0, 0, 0, 0
        min_x, min_y = self.points.min(axis=0)
        max_x, max_y = self.points.max(axis=0)
        return min_x, min_y, max_x, max_y

    def serialize(self):
        """Convert the ROI to a serializable dictionary"""
        # Convert numpy arrays to lists for serialization
        points_list = (
            self.points.tolist() if isinstance(self.points, np.ndarray) else []
        )
        geo_points_list = (
            self.geoPoints.tolist() if isinstance(self.geoPoints, np.ndarray) else None
        )

        # Convert array_slice and mean_spectrum to lists if they exist
        array_slice_list = array_slice_list = (
            self.arraySlice.tolist() if self.arraySlice is not None else None
        )

        mean_spectrum_list = (
            self.meanSpectrum.tolist() if self.meanSpectrum is not None else None
        )

        # convert color to tuple
        colorTuple = (
            self.color.red(),
            self.color.green(),
            self.color.blue(),
            self.color.alpha(),
        )
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode.name,
            "sourceImage": self.sourceImage,
            "points": points_list,
            "geoPoints": geo_points_list,
            "color": colorTuple,
            "visible": self.visible,
            "creationTime": self.creationTime.isoformat(),
            "description": self.description,
            "arraySlice": array_slice_list,
            "meanSpectrum": mean_spectrum_list,
            "customData": self.customData.serialize(),
        }

    @classmethod
    def deserialize(cls, data):
        """Create an ROI from a serialized dictionary"""
        inputKwargs = {}

        if data.get("id"):
            inputKwargs["id"] = data["id"]
        if data.get("name"):
            inputKwargs["name"] = data["name"]
        if data.get("mode"):
            inputKwargs["mode"] = ROIMode[data["mode"]]
        if data.get("sourceImage") is not None:
            inputKwargs["sourceImage"] = data["sourceImage"]

        points = data.get("points")
        if points is not None:
            inputKwargs["points"] = np.array(points)

        geo_points = data.get("geoPoints")
        if geo_points is not None:
            inputKwargs["geoPoints"] = np.array(geo_points)

        creationTime = data.get("creationTime")
        if creationTime:
            inputKwargs["creationTime"] = datetime.fromisoformat(creationTime)

        array_slice = data.get("arraySlice")
        if array_slice is not None:
            inputKwargs["arraySlice"] = np.array(array_slice)

        mean_spectrum = data.get("meanSpectrum")
        if mean_spectrum is not None:
            inputKwargs["meanSpectrum"] = np.array(mean_spectrum)

        color = data.get("color")
        if color is not None:
            inputKwargs["color"] = QColor(*color)

        visible = data.get("visible")
        if visible is not None:
            inputKwargs["visible"] = visible

        description = data.get("description")
        if description is not None:
            inputKwargs["description"] = description

        custom_data = data.get("customData")
        if custom_data is not None:
            inputKwargs["customData"] = ROICustomData.deserialize(custom_data)

        return cls(**inputKwargs)

    def clone(self):
        """Create a deep copy of the ROI"""
        return ROI.deserialize(self.serialize())

    def __str__(self):
        return f"ROI '{self.name}' ({self.id}) with {len(self.points)} points"


class GeoReferencer:
    """
    A class to handle georeferencing operations,
    converting between pixel coordinates and geographic coordinates (longitude/latitude)
    using a given affine transform and coordinate reference system (CRS).
    """

    def __init__(self, transform: Affine, crs: str):
        """
        Initializes the GeoReferencer with a given affine transform and CRS.

        Args:
            transform (Affine): The affine transformation matrix for the raster.
            crs (str): The coordinate reference system of the raster as WKT string.

        Raises:
            ValueError: If the CRS cannot be parsed or transformers cannot be created.
        """
        self.transform = transform
        self.crs = None
        self.toGeo = None
        self.fromGeo = None

        try:
            # Ensure the CRS is properly initialized from its WKT representation
            self.crs = CRS.from_wkt(crs)

            # Check if the CRS has a geodetic CRS for transformation
            if self.crs.geodetic_crs is None:
                logger.warning(f"CRS has no geodetic CRS, cannot create transformers")
                raise ValueError("CRS has no geodetic CRS")

            # transformer: map coordinates (meters) → geographic coordinates (longitude/latitude)
            self.toGeo = Transformer.from_crs(
                self.crs, self.crs.geodetic_crs, always_xy=True
            )
            # transformer: geographic coordinates → map coordinates
            self.fromGeo = Transformer.from_crs(
                self.crs.geodetic_crs, self.crs, always_xy=True
            )

        except (CRSError, ValueError) as e:
            logger.warning(f"Failed to create GeoReferencer: {e}")
            raise ValueError(f"Invalid CRS or unsupported coordinate system: {e}")

    def pixelToCoordinates(self, px: int, py: int) -> Tuple[float, float]:
        """
        Converts pixel coordinates to geographic coordinates (longitude, latitude).

        Args:
            px (int): The x-coordinate (column) of the pixel.
            py (int): The y-coordinate (row) of the pixel.

        Returns:
            Tuple[float, float]: The geographic coordinates (longitude, latitude).

        Raises:
            RuntimeError: If transformers are not available.
        """
        if self.toGeo is None:
            raise RuntimeError("Geographic transformation not available")

        # Convert pixel coordinates to map coordinates (x, y)
        x, y = rio.transform.xy(self.transform, px, py)
        # Transform map coordinates to geographic coordinates
        lon, lat = self.toGeo.transform(x, y)
        return lon, lat

    def coordinatesToPixel(self, lon: float, lat: float) -> Tuple[int, int]:
        """
        Converts geographic coordinates (longitude, latitude) to pixel coordinates.

        Args:
            lon (float): The longitude of the geographic coordinate.
            lat (float): The latitude of the geographic coordinate.

        Returns:
            Tuple[int, int]: The pixel coordinates (column, row) as integers.

        Raises:
            RuntimeError: If transformers are not available.
        """
        if self.fromGeo is None:
            raise RuntimeError("Geographic transformation not available")

        # Transform geographic coordinates to map coordinates (x, y)
        x, y = self.fromGeo.transform(lon, lat)
        # Convert map coordinates to pixel coordinates
        py, px = rio.transform.rowcol(self.transform, x, y)
        return int(px), int(py)


@dataclass
class Plot:
    """
    Attributes:
        plot_type (str): The type of plot (e.g., "ROI", "Histogram").
        timestamp (str): The time when the plot was saved.
        data (Any): Data needed to reconstruct the plot.
    """

    plot_type: str
    timestamp: str
    data: Any

    @staticmethod
    def create(roi: ROI):
        """Factory method to create a new plot with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Plot("ROI", timestamp, roi.meanSpectrum)


@attrs.define
class Color:
    r: float
    g: float
    b: float
    a: float

    @classmethod
    def black(cls):
        return cls(0.0, 0.0, 0.0, 1.0)

    @classmethod
    def white(cls):
        return cls(1.0, 1.0, 1.0, 1.0)

    def toQColor(self) -> QColor:
        c = self._as8bit()
        return QColor(c[0], c[1], c[2])

    def _as8bit(self):
        return (int(self.r * 255), int(self.g * 255), int(self.b * 255))


# --- Lazy import for Image alias. This basically just makes it so ---
def __getattr__(name):
    if name in ("Image", "VardaRaster"):
        globals()["Image"] = VardaRaster
        globals()["VardaRaster"] = VardaRaster
        return VardaRaster
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
