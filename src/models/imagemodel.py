"""
This module defines the ImageModel class, which serves as the base model for images
in the Varda application.
It provides a consistent interface for image data and includes signals and slots
for communication between the image model and other components.
"""

# standard library
import logging

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
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

    Properties:
        rasterData (np.ndarray): The raw image data.
        metadata (Metadata): Metadata associated with the image.
        stretch (tuple): The levels of the image.
        band (dict): The bands of the image.
        wavelength (list): The wavelengths of the image.
        bandCount (int): The number of bands in the image.
        imageSlice (np.ndarray): The image slice.
        imageType (str): The type of the image.
    """

    class Band(QObject):
        """
        Basic class to represents a band configuration.
        Use set() to modify, so it can emit a signal when changed
        """
        sigBandChanged = pyqtSignal()

        def __init__(self, r: int, g: int, b: int, name: str):
            super().__init__()
            self.values = (r, g, b)
            self.name = name

        def set(self, r, g, b):
            """Set the band values. Emits signal"""
            self.values = (r, g, b)
            self.sigBandChanged.emit()

        def save(self, outStream):
            """Save to the given DataStream."""
            for value in self.values:
                outStream.writeInt32(value)
            outStream.writeString(self.name)

        @classmethod
        def load(cls, inStream):
            """Read from the given DataStream, and construct a Band object."""
            r = inStream.readInt32()
            g = inStream.readInt32()
            b = inStream.readInt32()
            name = inStream.readString()
            return cls(r, g, b, name)

    class Stretch(QObject):
        """
        represents a stretch configuration.
        Use set() to modify, so it can emit a signal when changed
        """
        sigStretchChanged = pyqtSignal()

        def __init__(self, minR: int, maxR: int,
                           minG: int, maxG: int,
                           minB: int, maxB: int,
                           name: str
                     ):
            super().__init__()
            self.values = (minR, maxR), (minG, maxG), (minB, maxB)
            self.name = name

        def set(self, minR, maxR, minG, maxG, minB, maxB):
            """Set the stretch values. Emits signal"""
            self.values = (minR, maxR), (minG, maxG), (minB, maxB)
            self.sigStretchChanged.emit()

        def save(self, outStream):
            """Save to the given DataStream."""
            for valuePair in self.values:
                outStream.writeInt32(valuePair[0])
                outStream.writeInt32(valuePair[1])
            outStream.writeString(self.name)

        @classmethod
        def load(cls, inStream):
            """Read from the given DataStream, and construct a Stretch object."""
            values = (inStream.readInt32(), inStream.readInt32()), \
                     (inStream.readInt32(), inStream.readInt32()), \
                     (inStream.readInt32(), inStream.readInt32())
            name = inStream.readString()
            return cls(*values, name)

    sigRoiChanged = pyqtSignal()      # Signal when ROI changes
    sigBandChanged = pyqtSignal()     # Signal when band adjustments change
    sigStretchChanged = pyqtSignal()  # Signal when the stretch changes
    sigImageChanged = pyqtSignal()    # Signal when anything about the image changes
    sigImageDestroyed = pyqtSignal()  # Signal when the image is destroyed

    def __init__(self, rasterData, metadata):
        """
        Initialize the ImageModel with raster data and metadata

        Args:
            rasterData (np.ndarray): The raw image data.
            metadata (Metadata): Metadata associated with the image.
        """
        super().__init__()

        self._rasterData = rasterData
        self._metadata = metadata

        self._band = [self.Band(0, 0, 0, "mono"), self.Band(0, 1, 2, "rgb"),
                      self.Band(10, 20, 30, "custom1")]

        self._stretch = [self.Stretch(0, 1, 0, 1, 0, 1, "0-1"),
                         self.Stretch(0, 255, 0, 255, 0, 255, "0-255")]

        self._connectSignals()

    def _connectSignals(self):
        """Make all signals trigger the imageChanged signal."""
        self.sigBandChanged.connect(self.sigImageChanged.emit)
        self.sigStretchChanged.connect(self.sigImageChanged.emit)
        self.sigRoiChanged.connect(self.sigImageChanged.emit)

    @property
    def rasterData(self) -> np.ndarray:
        """Get the raster data of the image."""
        return self._rasterData

    @property
    def metadata(self):
        """Get the metadata of the image."""
        return self._metadata

    @property
    def stretch(self):
        """Get the levels of the image."""
        return self._stretch

    @property
    def defaultStretch(self):
        """Get the default stretch of the image."""
        return self._stretch[0]

    @property
    def band(self):
        """Get the bands of the image."""
        return self._band

    @property
    def defaultBand(self):
        """Get the default bands of the image."""
        return self._band[0]

    @property
    def bandCount(self) -> int:
        """Get the number of bands in the image."""
        return self.rasterData.shape[2]

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
        return list(range(self.bandCount))

    @property
    def imageType(self) -> str:
        """Get the type of the image (mono, rgba, spectral)."""
        if self.bandCount == 1:
            return "mono"
        if self.bandCount in {3, 4}:
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
        except TypeError as exc:
            msg = "Error getting imageSlice"
            logger.exception(msg)
            raise TypeError from exc

    def save(self, out):
        """
        Save the image data to an output stream.

        Args:
            out (QDataStream): The output stream.
        """
        self.metadata.save(out)
        for band in self.band:
            band.save(out)
        for stretch in self.stretch:
            stretch.save(out)

    def load(cls, inStream):
        """
        Load session data for this image model from an input stream.
        This includes metadata, bands, and stretches.
        The raster data should be loaded from the original file.

        Args:
            inStream (QDataStream): The input stream.

        Returns:
            ImageModel: The loaded image model.
        """
        metadata = Metadata.load(inStream)
        bands = [cls.Band.load(inStream) for _ in range(3)]
        stretches = [cls.Stretch.load(inStream) for _ in range(2)]

        return cls(None, metadata)

    def __str__(self):
        return "name: " + self.__class__.__name__

    def __repr__(self):
        return self.__str__()
