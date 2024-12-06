"""
This module defines the ImageModel class, which serves as the base model for images in the Varda application.
It provides a consistent interface for image data and includes signals and slots for communication between the image model and other components.

Classes:
    ImageModel: Represents an image model with attributes for raster data, metadata, and various image properties.
"""

# standard library
from dataclasses import dataclass
import logging

# third party imports
# pylint: disable=no-name-in-module
from PyQt6.QtCore import QObject, pyqtSignal, Qt, pyqtSlot
import pyqtgraph as pg
import numpy as np

# local imports
from models.metadata import Metadata

logger = logging.getLogger(__name__)


class ImageModel(QObject):
    """
    Base model for images in varda.
    Allows for a consistent interface with the images. Provides a set of signals and
    slots for information exchange between the image and other views.

    Attributes:
        sigRoiChanged (pyqtSignal): Signal when ROI changes.
        sigBandChanged (pyqtSignal): Signal when band adjustments change.
        sigStretchChanged (pyqtSignal): Signal when the stretch changes.
        sigImageChanged (pyqtSignal): Signal when anything about the image changes.
        sigImageDestroyed (pyqtSignal): Signal when the image is destroyed.
        rasterData (np.ndarray): The raw image data.
        metadata (Metadata): Metadata associated with the image.
        stretch (tuple): The levels of the image.
        band (dict): The bands of the image.
        wavelength (list): The wavelengths of the image.
        bandCount (int): The number of bands in the image.
        imageSlice (np.ndarray): The image slice.
        imageType (str): The type of the image.
        normalized_data (np.ndarray): The normalized data of the image.
    Properties:

    Public Methods:
        __init__(self, rasterData, metadata, defaults=None)
        connectSignals(self)
        imageItem(self)
        process(self, process)
        __str__(self)
        __repr__(self)
        __del__(self)
    """

    class Band(QObject):
        sigBandChanged = pyqtSignal()
        def __init__(self, r: int, g: int, b: int, name: str):
            super().__init__()
            self.r = r
            self.g = g
            self.b = b
            self.name = name

        def set(self, r, g, b):
            self.r = r
            self.g = g
            self.b = b
            self.sigBandChanged.emit()

        @property
        def values(self):
            return self.r, self.g, self.b

    class Stretch(QObject):
        sigStretchChanged = pyqtSignal()

        def __init__(self, minR: int, maxR: int,
                           minG: int, maxG: int,
                           minB: int, maxB: int,
                           name: str
                           ):
            super().__init__()
            self.minR = minR
            self.maxR = maxR
            self.minG = minG
            self.maxG = maxG
            self.minB = minB
            self.maxB = maxB
            self.name = name

        def set(self, minR, maxR, minG, maxG, minB, maxB):
            self.minR = minR
            self.maxR = maxR
            self.minG = minG
            self.maxG = maxG
            self.minB = minB
            self.maxB = maxB
            self.sigStretchChanged.emit()

        @property
        def values(self):
            return (self.minR, self.maxR), (self.minG, self.maxG), (self.minB, self.maxB)


    sigRoiChanged = pyqtSignal()  # Signal when ROI changes
    sigBandChanged = pyqtSignal()  # Signal when band adjustments change
    sigStretchChanged = pyqtSignal()  # Signal when the stretch changes
    sigImageChanged = pyqtSignal()  # Signal when anything about the image changes
    sigImageDestroyed = pyqtSignal()  # Signal when the image is destroyed

    def __init__(self, rasterData, metadata, defaults=None):
        """
        Initialize the ImageModel with raster data, metadata, and optional defaults.

        Args:
            rasterData (np.ndarray): The raw image data.
            metadata (Metadata): Metadata associated with the image.
            defaults (dict, optional): Default settings for band, stretch, and other
            tables. Primarily used for testing.
        """
        super().__init__()

        # probably won't keep this
        self._normalized_data = None

        self._rasterData = rasterData
        self._metadata = metadata

        # self._metadataTable = None
        # self._bandTable = None
        # self._stretchTable = None
        # self._ROITable = None
        # self.initInnerModels(defaults)

        self._band = [self.Band(0, 0, 0, "mono"), self.Band(0, 1, 2, "rgb"),
                      self.Band(10,20, 30, "custom1")]

        self._stretch = [self.Stretch(0, 1, 0, 1, 0, 1, "0-1"),
                         self.Stretch(0, 255, 0, 255, 0, 255, "0-255")]

        self.connectSignals()

    def connectSignals(self):
        """
        Connect signals to slots for the image model.
        """
        self.sigBandChanged.connect(self.sigImageChanged.emit)
        self.sigStretchChanged.connect(self.sigImageChanged.emit)
        self.sigRoiChanged.connect(self.sigImageChanged.emit)

    @property
    def rasterData(self) -> np.ndarray:
        """
        Get the raster data of the image.
        """
        return self._rasterData

    @property
    def metadata(self) -> Metadata:
        """
        Get the metadata of the image.

        Returns:
            Metadata: The metadata.
        """
        return self._metadata

    @property
    def stretch(self):
        """
        Get the levels of the image.

        Returns:
            tuple: The levels of the image.
        """
        return self._stretch

    @property
    def defaultStretch(self):
        """
        Get the default stretch of the image.

        Returns:
            Stretch: The default stretch of the image.
        """
        return self._stretch[0]

    @property
    def band(self):
        """
        Get the bands of the image.

        Returns:
            list: The bands of the image.
        """
        return self._band

    @property
    def defaultBand(self):
        """
        Get the default bands of the image.

        Returns:
            Band: The default bands of the image.
        """
        return self._band[0]

    @property
    def wavelength(self):
        """
        Get the name/values of all wavelengths in the image.
        If the metadata doesn't have a wavelength, return the range of
        bandCount

        Returns:
            list: (int | float | str) The wavelengths of the image.
        """
        if self.metadata.wavelength:
            return self.metadata.wavelength
        return [i for i in range(self.bandCount)]

    @property
    def bandCount(self) -> int:
        """
        Get the number of bands in the image.

        Returns:
            int: The number of bands.
        """
        return self.rasterData.shape[2]

    @property
    def imageType(self) -> str:
        """
        Get the type of the image (mono, rgba, spectral).

        Returns:
            str: The type of the image.
        """
        if self.bandCount == 1:
            return "mono"
        if self.bandCount == 3 or self.bandCount == 4:
            return "rgba"
        if self.bandCount > 4:
            return "spectral"
        return "unknown"

    def getRasterDataSlice(self, bandIndex) -> np.ndarray:
        """
        Returns a 3 band image slice using the specified band index.

        Args:
            bandIndex: The band index.

        Returns:
            np.ndarray: The image slice.
        """
        if any(isinstance(item, float) for item in bandIndex):
            logger.warning("Band index contains a float. Converting to int.")
            bandIndex = [int(item) for item in bandIndex]

        try:
            return self.rasterData[:, :, bandIndex]
        except TypeError:
            msg = "Error getting imageSlice"
            logger.exception(msg)
            raise TypeError

    # @property
    # def normalized_data(self):
    #     """
    #     Get the normalized data of the image.
    #
    #     Returns:
    #         np.ndarray: The normalized data.
    #     """
    #     if self._normalized_data is not None:
    #         return self._normalized_data
    #
    #     self._normalized_data = ((self.rasterData - np.min(self.rasterData)) /
    #                              (np.max(self.rasterData) - np.min(self.rasterData)))
    #     return self._normalized_data

    @pyqtSlot()
    def process(self, process):
        """
        Execute a process on the image.

        Args:
            process: The process to execute.
        """
        pass

    def __str__(self):
        """
        Get the string representation of the class.

        Returns:
            str: The string representation of the class.
        """
        return "name: " + self.__class__.__name__

    def __repr__(self):
        """
        Get the string representation of the class for debugging.
        (for now just the same as __str__)

        Returns:
            str: The string representation of the class for debugging.
        """
        return self.__str__()

    def __del__(self):
        """
        Emit the imageDestroyed signal when the object is deleted. So any views
        dependent on this can clean up.
        """
        self.sigImageDestroyed.emit()
