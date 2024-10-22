# standard library
from typing import Optional

# third-party imports
import numpy as np
from affine import Affine

# local imports
import vardaconfig


class Metadata():
    """
    A standardized set of metadata for images. driver, dtype, dataignore, width,
    height, bandcount, and transform, are expected to be provided by every image.
    **kwargs lets you add additional metadata properties for displaying and editing.

    individual sections of metadata can be accessed using dot-notation.
    the entire metadata object can also be iterated through as if it were a dictionary
    """

    def __init__(self,
                 driver: str,
                 dtype: str,
                 dataignore: float,
                 width: int,
                 height: int,
                 bandcount: int,
                 default_bands: dict,
                 transform: Affine,
                 wavelength: np.ndarray,
                 **kwargs):
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

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def __repr__(self):
        out = "Metadata:\n"
        for key, value in self:
            out += "    " + f"{key}: {value}" + "\n"
        return out
