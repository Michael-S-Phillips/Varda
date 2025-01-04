# standard library
import logging
from typing import Any, List
from enum import Enum

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np

# local imports
from core.entities import Image, Metadata, Band, Stretch

logger = logging.getLogger(__name__)


class ProjectContext(QObject):
    """TODO:"""

    class ChangeType(Enum):
        """Simple enumerator to representing the types of data that can be changed"""

        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"

    # signal that emits when something writes to the projectContext.
    # int argument is the index of the item that was changed.
    sigDataChanged = pyqtSignal(int, ChangeType)

    _images: List[Image]

    def __init__(self):
        super().__init__()
        self._images = []

    # Image Access
    def getImage(self, index):
        """Retrieve an image by index."""
        return self._images[index]

    def addImage(self, image: Image):
        """Add a new image to the context."""
        self._images.append(image)
        index = len(self._images) - 1
        self._emitChange(index, self.ChangeType.IMAGE)
        return index

    def createImage(
        self,
        raster: np.ndarray,
        metadata: Metadata,
        stretch: List[Stretch] = None,
        band: List[Band] = None,
    ):
        """Creates a new image with optional defaults for stretch, adding it to the
        project. Unless we're loading from an existing project, a newly
        loaded image usually won't have stretch and band data associated with it yet
        """
        image = Image(
            raster,
            metadata,
            stretch if stretch else [Stretch.createDefault()],
            band if band else [Band.createDefault()],
            len(self._images),
        )
        if len(image.stretch) == 0:
            logger.warning("Image Stretch list is empty. this may cause errors.")
        if len(image.band) == 0:
            logger.warning("Image Band list is empty. this may cause errors.")
        return self.addImage(image)

    def removeImage(self, index):
        """Remove an image by index."""
        self._images.pop(index)
        self._emitChange(index, self.ChangeType.IMAGE)

    def getAllImages(self):
        """Retrieve a list of all the images in the project"""
        return self._images

    # Metadata
    def updateMetadata(self, index, key: str, value: Any):
        """Update a metadata field."""
        metadata = self._images[index].metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
        self._emitChange(index, self.ChangeType.METADATA)

    # Stretch Management
    def addStretch(self, index, stretch: Stretch):
        """Add a stretch to an image."""
        self._images[index].stretch.append(stretch)
        self._emitChange(index, self.ChangeType.STRETCH)

    def removeStretch(self, index, stretchIndex):
        """Remove a stretch by index from an image."""
        self._images[index].stretch.pop(stretchIndex)
        self._emitChange(index, self.ChangeType.STRETCH)

    def updateStretch(
        self,
        imageIndex: int,
        stretchIndex: int,
        minR: int = None,
        maxR: int = None,
        minG: int = None,
        maxG: int = None,
        minB: int = None,
        maxB: int = None,
    ):
        image = self.getImage(imageIndex)
        oldStretch = image.stretch[stretchIndex]

        # Create the updated Stretch using existing values as fallbacks
        newStretch = Stretch(
            name=oldStretch.name,  # Name stays the same
            minR=minR if minR is not None else oldStretch.minR,
            maxR=maxR if maxR is not None else oldStretch.maxR,
            minG=minG if minG is not None else oldStretch.minG,
            maxG=maxG if maxG is not None else oldStretch.maxG,
            minB=minB if minB is not None else oldStretch.minB,
            maxB=maxB if maxB is not None else oldStretch.maxB,
        )
        # replace the Stretch
        self._images[imageIndex].stretch[stretchIndex] = newStretch
        self._emitChange(imageIndex, self.ChangeType.STRETCH)

    def replaceStretch(self, index, stretchIndex, newStretch: Stretch):
        """Update a specific stretch."""
        self._images[index].stretch[stretchIndex] = newStretch
        self._emitChange(index, self.ChangeType.STRETCH)

    # Band Management
    def addBand(self, index, band: Any):
        """Add a band to an image."""
        self._images[index].band.append(band)
        self._emitChange(index, self.ChangeType.BAND)

    def removeBand(self, index, bandIndex):
        """Remove a band by index from an image."""
        self._images[index].band.pop(bandIndex)
        self._emitChange(index, self.ChangeType.BAND)

    def updateBand(
        self,
        index,
        bandIndex,
        name: str = None,
        r: int = None,
        g: int = None,
        b: int = None,
    ):
        image = self.getImage(index)
        oldBand = image.band[bandIndex]
        newBand = Band(
            name=name if name else oldBand.name,
            r=r if r else oldBand.r,
            g=g if g else oldBand.g,
            b=b if b else oldBand.b,
        )
        # Replace the band
        self._images[index].band[bandIndex] = newBand
        self._emitChange(index, self.ChangeType.BAND)
        logger.debug(
            f"Updated Band.\n"
            f"  old: {oldBand.r}, {oldBand.g}, {oldBand.b}\n"
            f"  new:  {newBand.r}, {newBand.g}, {newBand.b}"
        )

    # Helper methods
    def _emitChange(self, index, changeType):
        self.sigDataChanged.emit(index, changeType)
