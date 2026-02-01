"""
entities.py: data structures used throughout Varda
"""

# standard library
from __future__ import annotations
from dataclasses import dataclass, field
import logging
from typing import Any, Dict, Protocol, Tuple, Type, Optional, override
from datetime import datetime
import uuid
from enum import Enum
from functools import lru_cache, cached_property

# third party imports
import attrs
import affine
from affine import Affine
import numpy as np
import geopandas as gpd
from PyQt6.QtGui import QColor
import rasterio as rio
from rasterio.windows import Window
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError


logger = logging.getLogger(__name__)


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

    @values.validator
    def _check_values(self, attribute, value):
        if value.ndim != 1:
            raise ValueError(f"values must be a 1d array, got {value.ndim}d array")


class DataSource(Protocol):
    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray: ...

    def getWindow(self, x1, y1, x2, y2) -> np.ndarray: ...

    def getBands(self, bandIndices: list[int]) -> np.ndarray: ...

    def getData(
        self,
        bandIndices: list[int] | None = None,
        window: Tuple[int, int, int, int] | None = None,
    ) -> np.ndarray: ...

    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...

    @property
    def bandCount(self) -> int: ...

    @property
    def bandNames(self) -> list[str]: ...

    @property
    def wavelengthUnits(self) -> str: ...

    @property
    def isParameterized(self) -> bool: ...


class RasterioDataSource(DataSource):
    def __init__(self, filePath: str):
        self.filePath = filePath
        self.src = rio.open(filePath)

    @lru_cache(maxsize=128)
    def getPixelSpectrum(self, x: int, y: int) -> np.ndarray:
        if x < 0 or x >= self.src.width or y < 0 or y >= self.src.height:
            raise IndexError("Pixel coordinates out of bounds")

        return (
            self.src.read(window=Window(x, y, 1, 1), masked=True)
            .filled(np.nan)
            .squeeze()
        )

    def getWindow(self, x1, y1, x2, y2) -> np.ndarray:
        return self.src.read(window=Window(x1, y1, x2 - x1, y2 - y1))

    def getBands(self, bandIndices: list[int]) -> np.ndarray:
        if len(bandIndices) == 1:
            return self.src.read(bandIndices[0] + 1)
        else:
            return self.src.read([i + 1 for i in bandIndices])

    def getData(
        self,
        bandIndices: list[int] | None = None,
        window: Tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """get raster data, with optional constraints on bands and window"""
        bands: int | list[int] | None
        if bandIndices is None:
            bands = None
        elif len(bandIndices) == 1:
            bands = bandIndices[0] + 1
        else:
            bands = [i + 1 for i in bandIndices]

        return self.src.read(bands, window=window)

    @property
    def width(self):
        return self.src.width

    @property
    def height(self):
        return self.src.height

    @property
    def bandCount(self):
        return self.src.count

    @cached_property
    def bandNames(self):
        return [wl.strip() for wl in self.src.tags()["wavelengths"].split(",")]

    @cached_property
    def wavelengthUnits(self):
        return self.src.tags().get("wavelength_units", "Unknown")

    @property
    def isParameterized(self):
        """I'm making the assumption for now that parameter images will always be in ENVI format."""
        return False


class ENVIDataSource(RasterioDataSource):
    def __init__(self, filepath: str):
        super().__init__(filepath)
        self.envi_metadata = self.src.tags(ns="ENVI")

    @cached_property
    def bandNames(self) -> list[str]:
        if "band_names" in self.envi_metadata:
            return [
                name.strip()
                for name in self.envi_metadata["band_names"].strip("{}").split(",")
            ]
        elif "wavelength" in self.envi_metadata:
            return [
                w.strip()
                for w in self.envi_metadata["wavelength"].strip("{}").split(",")
            ]
        else:
            return [f"Band {i + 1}" for i in range(self.src.count)]

    @cached_property
    def wavelengthUnits(self) -> str:
        return self.envi_metadata.get("wavelength_units", "Unknown")

    @cached_property
    def isParameterized(self) -> bool:
        return "band_names" in self.envi_metadata


if __name__ == "__main__":
    from pathlib import Path
    from varda.utilities.debug import Profiler

    logging.getLogger("rasterio").setLevel(logging.CRITICAL)

    filepath = (
        "~/PycharmProjects/Varda/testImages/Data/CRISM/frt00012dfa_07_if164j_mtr3.img"
    )
    filepath = str(Path(filepath).expanduser())
    profile = Profiler()
    datasource = RasterioDataSource(filepath)
    profile("time to open image")
    spectrum = datasource.getPixelSpectrum(774, 766)
    profile("time to get a pixel spectrum")

    spectrum2 = datasource.getPixelSpectrum(774, 766)
    profile("time to get the same pixel spectrum again")
    spectrum3 = datasource.getPixelSpectrum(700, 700)
    profile("time to get a closeby pixel spectrum")
    spectrum4 = datasource.getPixelSpectrum(0, 0)
    profile("time to get a very different pixel spectrum")
    print(spectrum)
    print((datasource.height, datasource.width, datasource.bandCount))


@attrs.define(slots=True)
class VardaRaster:
    _dataSource: DataSource

    def getPixelSpectrum(self, x: int, y: int) -> Spectrum:
        """Get the spectrum at a specific pixel location (x, y)"""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError("Pixel coordinates out of bounds")
        return Spectrum(
            values=self._dataSource.getPixelSpectrum(x, y),
            wavelengths=self.bandWavelengths,
        )

    def getBands(self, bandIndices: list[int]) -> np.ndarray:
        """Get the raster data for specific bands"""
        if np.any(np.asarray(bandIndices) >= self.bandCount):
            raise IndexError("Requested band indices are out of bounds")
        return self._dataSource.getBands(bandIndices)

    def getData(
        self,
        bandIndices: list[int] | None = None,
        window: Tuple[int, int, int, int] | None = None,
    ) -> np.ndarray:
        """get raster data, with optional constraints on bands and window"""
        if bandIndices is not None and np.any(
            np.asarray(bandIndices) >= self.bandCount
        ):
            raise IndexError("Requested band indices are out of bounds")
        if window is not None and (
            window[0] < 0
            or window[1] < 0
            or window[2] > self.width
            or window[3] > self.height
        ):
            raise ValueError("Requested window is out of bounds")
        return self._dataSource.getData(bandIndices, window)

    @property
    def height(self):
        return self._dataSource.height

    @property
    def width(self):
        return self._dataSource.width

    @property
    def bandCount(self):
        return self._dataSource.bandCount

    @property
    def bandNames(self):
        return self._dataSource.bandNames

    @property
    def bandWavelengths(self):
        if self.bandMask is not None:
            return self._dataSource.bandWavelengths[self.bandMask]
        else:
            return self._dataSource.bandWavelengths

    @property
    def wavelengthUnits(self):
        return self._dataSource.wavelengthUnits

    @property
    def isParameterImage(self):
        return self._dataSource.bandNames


@attrs.define(slots=True)
class VardaSubsetRaster(VardaRaster):
    _dataSource: DataSource
    # window format: (x1, y1, x2, y2)
    window: tuple[int, int, int, int] | None = attrs.field(default=None)
    # indices of bands to include
    bandMask: np.ndarray | None = attrs.field(default=None)

    @window.validator
    def _check_window(self, attribute, value):
        if value is None:
            return
        x1, y1, x2, y2 = value
        if (
            x1 < 0
            or y1 < 0
            or x2 > self._dataSource.width
            or y2 > self._dataSource.height
        ):
            raise ValueError("window is out of bounds of the raster dimensions")
        if x2 <= x1 or y2 <= y1:
            raise ValueError("window cannot have non-positive width or height")

    @bandMask.validator
    def _check_bandMask(self, attribute, value):
        if value is None:
            return
        if np.any(value < 0) or np.any(value >= self._dataSource.bandCount):
            raise ValueError("bandMask contains invalid band indices")

    def getPixelSpectrum(self, x: int, y: int) -> Spectrum:
        """Get the spectrum at a specific pixel location (x, y) in the subset raster"""
        if x < self.xStart or x >= self.xEnd or y < self.yStart or y >= self.yEnd:
            raise IndexError("Pixel coordinates out of bounds")
        return super().getPixelSpectrum(x, y)

    def getBands(self, bandIndices: list[int]) -> np.ndarray:
        """Get the raster data for specific bands in the subset raster"""
        if self.bandMask is not None and not np.isin(bandIndices, self.bandMask).all():
            raise IndexError("Requested band indices are not in the band mask")
        return self._dataSource.getData(bandIndices, self.window)

    @property
    def bandCount(self):
        if self.bandMask is not None:
            return len(self.bandMask)
        else:
            return self._dataSource.bandCount

    @property
    def height(self):
        return self.yEnd - self.yStart

    @property
    def width(self):
        return self.xEnd - self.xStart

    @property
    def xStart(self):
        return self.window[0]

    @property
    def xEnd(self):
        return self.window[2]

    @property
    def yStart(self):
        return self.window[1]

    @property
    def yEnd(self):
        return self.window[3]


@dataclass
class Image:
    """data container representing an Image object in Varda

    Attributes:
        raster (np.ndarray): a 3d array storing the raster (pixel) data of an image.
        metadata: The metadata associated with an image (See Metadata for details).
        index: A unique identifier for the image. Mainly to be used for comparisons.
    """

    raster: np.ndarray
    metadata: Metadata

    @property
    def height(self):
        return self.raster.shape[0]

    @property
    def width(self):
        return self.raster.shape[1]

    def getSpectrum(self, x: int, y: int) -> Spectrum:
        """Get the spectrum at a specific pixel location (x, y)"""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            raise IndexError("Pixel coordinates out of bounds")
        values = self.raster[y, x, :]
        wavelengths = self.metadata.wavelengths
        return Spectrum(values=values, wavelengths=wavelengths)


# standard library


# local imports


logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
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


logger = logging.getLogger(__name__)


class ROIMode(Enum):
    """Enum to define different ROI drawing modes"""

    FREEHAND = 0
    RECTANGLE = 1
    ELLIPSE = 2
    POLYGON = 3  # Click-by-click polygon


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
