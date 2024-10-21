# standard library
import time
from typing import override
from abc import ABC, abstractmethod

# third party imports
import numpy as np
import rasterio as rio

class Image(ABC):
    """
    Abstract base class for all images in varda.
    Allows for a consistent interface with the images.
    """

    # dictionary of all subclasses of SpectralImage, mapped to their associated keyword
    subclasses = []

    # this forces subclasses to set this value
    @property
    @abstractmethod
    def image_type(self):
        pass

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        Image.subclasses.append(cls)

    """
    Getters that all image subclasses must provide:
        data -  ndarray containing the raw image data
        meta -  Metadata dictionary
    """

    @property
    @abstractmethod
    def data(self):
        return self._data

    @property
    @abstractmethod
    def meta(self):
        return self._meta
