# standard library
from typing import Any, Dict
from dataclasses import dataclass, field

# third-party imports
import numpy as np


# local imports
from .band import Band


# pylint: disable=too-many-instance-attributes
@dataclass
class Metadata:
    """Data container representing the metadata of an image.

    This ensures that every image contains a standard base set of metadata,
    but allows for adding extra metadata items via _extraMetadata.

    Note that this data container is mutable, But do not directly modify its contents.
    use ProjectContext to edit it so that the program knows when it's changed.
    """
    _filename: str = ""
    _driver: str = ""
    _width: int = 0
    _height: int = 0
    _dtype: str = ""
    _dataIgnore: float = 0
    _bandCount: int = 0
    _defaultBand: Band = field(default_factory=Band.createDefault)
    _wavelength: np.ndarray = field(default_factory=lambda: np.zeros(0))
    _extraMetadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def filename(self):
        """read-only property for driver"""
        return self._filename

    @property
    def driver(self):
        """read-only property for driver"""
        return self._driver

    @property
    def width(self):
        """read-only property for width"""
        return self._width

    @property
    def height(self):
        """read-only property for height"""
        return self._height

    @property
    def dtype(self):
        """read-only property for dtype"""
        return self._dtype

    @property
    def dataIgnore(self):
        """read-only property for dataIgnore"""
        return self._dataIgnore

    @property
    def bandCount(self):
        """read-only property for bandCount"""
        return self._bandCount

    @property
    def defaultBand(self):
        """read-only property for defaultBand"""
        return self._defaultBand

    @property
    def wavelength(self):
        """read-only property for wavelength"""
        return self._wavelength

    @property
    def extraMetadata(self):
        """read-only property for extraMetadata"""
        return self._extraMetadata

    # other methods
    def toDict(self):
        """generate a flat dict containing all the metadata and extra metadata"""
        coreMetadata = {
            key: value for key, value in self.__dict__.items() if key != "extraMetadata"
        }
        return {**coreMetadata, **self.extraMetadata}

    # magic methods to add the ability to iterate through the items
    def __iter__(self):
        items = self.toDict()
        for attr, value in items:
            yield attr, value

    def __repr__(self):
        allItems = self.toDict()
        out = "Metadata:\n"
        for key, value in allItems.items():
            out += "    " + f"{key}: {value}" + "\n"
        return out

    def __getitem__(self, item):
        return self.toDict().get(item)

