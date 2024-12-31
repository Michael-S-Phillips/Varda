# standard library
from typing import Any, Dict
from dataclasses import dataclass, field

# third-party imports
from affine import Affine
import numpy as np
from dataclasses import dataclass


# local imports


@dataclass
class Metadata:
    _driver: str = ""
    _width: int = 0
    _height: int = 0
    _dtype: str = ""
    _dataIgnore: float = 0
    _bandCount: int = 0
    _defaultBands: Dict[str, int] = field(default_factory=dict)
    _wavelength: np.ndarray = np.zeros((1, 0))
    _extraMetadata: Dict[str, Any] = field(default_factory=dict)

    # Read-only properties for core metadata
    @property
    def driver(self):
        return self._driver

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def dtype(self):
        return self._dtype

    @property
    def dataIgnore(self):
        return self._dataIgnore

    @property
    def bandCount(self):
        return self._bandCount

    @property
    def defaultBands(self):
        return self._defaultBands

    @property
    def wavelength(self):
        return self._wavelength

    @property
    def extraMetadata(self):
        return self._extraMetadata

    # other methods
    def to_dict(self):
        coreMetadata = {
            key: value for key, value in self.__dict__.items() if key != "extraMetadata"
        }
        return dict(**coreMetadata, **self.extraMetadata)

    # magic methods to add the ability to iterate through the items
    def __iter__(self):
        items = self.to_dict()
        for attr, value in items:
            yield attr, value

    def __repr__(self):
        items = self.to_dict()
        out = "Metadata:\n"
        for key, value in items:
            out += "    " + f"{key}: {value}" + "\n"
        return out


class Metadata:
    """
    A standardized set of metadata for images. driver, dtype, dataignore, width,
    height, bandcount, and transform, are expected to be provided by every image.
    **kwargs lets you add additional metadata properties for displaying and editing.

    individual sections of metadata can be accessed using dot-notation.
    the entire metadata object can also be iterated through as if it were a dictionary
    """

    def __init__(
        self,
        driver: str,
        dtype: str,
        dataignore: float,
        width: int,
        height: int,
        bandcount: int,
        default_bands: dict,
        transform: Affine,
        wavelength: np.ndarray,
        **kwargs,
    ):
        super().__init__()

        if default_bands is None:
            default_bands = {}
        if transform is None:
            transform = Affine.identity()
        if wavelength is None:
            wavelength = np.array([])

        # set base args
        self.driver = driver
        self.dtype = dtype
        self.dataignore = dataignore
        self.width = width
        self.height = height
        self.bandcount = bandcount
        self.default_bands = default_bands

        self.transform = transform
        self.wavelength = wavelength

        # add additional args
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
        self.numExtraArgs = len(kwargs)

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def __repr__(self):
        out = "Metadata:\n"
        for key, value in self:
            out += "    " + f"{key}: {value}" + "\n"
        return out
