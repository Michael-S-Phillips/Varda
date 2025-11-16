# standard library
from typing import Any, Dict, Type
from dataclasses import dataclass, field

import affine

# third-party imports
import numpy as np
import logging

from affine import Affine
from pyproj import CRS

from .geo_referencer import GeoReferencer

# local imports
from .band import Band

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
    name: str = ""  # Added a name field for display purposes
    transform: Affine = affine.identity
    crs: CRS = None
    geoReferencer: GeoReferencer = None

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
        if not isinstance(self.defaultBand, Band):
            raise self.BadMetadataError("defaultBand", "Band", self.defaultBand)
        if not isinstance(self.wavelengths, np.ndarray):
            raise self.BadMetadataError("wavelengths", "np.ndarray", self.wavelengths)
        if self.geoReferencer is not None and not isinstance(
            self.geoReferencer, GeoReferencer
        ):
            raise self.BadMetadataError(
                "geoReference", "GeoReference", self.geoReferencer
            )
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
        for field in expected_fields:
            if field in kwargs:
                setattr(self, field, kwargs.pop(field))
            elif field == "extraMetadata":
                # Initialize extraMetadata if not provided
                self.extraMetadata = kwargs.pop("extraMetadata", {})

        # Move any remaining unexpected kwargs to extraMetadata
        for key, value in kwargs.items():
            logger.warning(f"Unexpected keyword argument '{key}' moved to extraMetadata")
            self.extraMetadata[key] = value

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
            defaultBand=Band.deserialize(data["defaultBand"]),
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
