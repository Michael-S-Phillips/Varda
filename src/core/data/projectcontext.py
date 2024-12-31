# standard library
import logging
from typing import Any
from enum import Enum

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np

# local imports
from core.entities import Image, Stretch, Band

logger = logging.getLogger(__name__)


class ProjectContext(QObject):

    class ChangeType(Enum):
        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"
        RASTER = "raster"

    # signal that emits when something writes to the projectContext.
    # int argument is the index of the item that was changed.
    sigDataChanged = pyqtSignal(int, ChangeType)

    def __init__(self):
        super().__init__()
        self._images = []

    # Image Access
    def getImage(self, index: int) -> Image:
        """Retrieve an image by index."""
        return self._images[index]

    def addImage(self, image: Image):
        """Add a new image to the context."""
        self._images.append(image)
        self.emitChange(len(self._images) - 1, self.ChangeType.IMAGE)

    def removeImage(self, index: int):
        """Remove an image by index."""
        self._images.pop(index)
        self.emitChange(index, self.ChangeType.IMAGE)

    def getAllImages(self):
        """Retrieve a list of all the images in the project"""
        return self._images

    # Raster Data
    def updateRasterData(self, index: int, new_raster: np.ndarray):
        """Update the raster data of an image."""
        self._images[index]._raster = new_raster
        self.emitChange(index, self.ChangeType.RASTER)

    # Metadata
    def updateMetadata(self, index: int, key: str, value: Any):
        """Update a metadata field."""
        metadata = self._images[index].metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
        self.emitChange(index, self.ChangeType.METADATA)

    # Stretch Management
    def addStretch(self, index: int, stretch: Stretch):
        """Add a stretch to an image."""
        self._images[index].stretch.append(stretch)
        self.emitChange(index, self.ChangeType.STRETCH)

    def removeStretch(self, index: int, stretchIndex: int):
        """Remove a stretch by index from an image."""
        self._images[index].stretch.pop(stretchIndex)
        self.emitChange(index, self.ChangeType.STRETCH)

    def updateStretch(self, index: int, stretchIndex: int, newStretch: Stretch):
        """Update a specific stretch."""
        self._images[index].stretch[stretchIndex] = newStretch
        self.emitChange(index, self.ChangeType.STRETCH)

    # Band Management
    def addBand(self, index: int, band: Any):
        """Add a band to an image."""
        self._images[index].band.append(band)
        self.emitChange(index, self.ChangeType.BAND)

    def removeBand(self, index: int, bandIndex: int):
        """Remove a band by index from an image."""
        self._images[index].band.pop(bandIndex)
        self.emitChange(index, self.ChangeType.BAND)

    def updateBand(self, index: int, bandIndex: int, newBand: Band):
        """Update a specific band."""
        self._images[index].band[bandIndex] = newBand
        self.emitChange(index, self.ChangeType.BAND)

    # Helper methods

    def emitChange(self, index, changeType):
        self.sigDataChanged.emit(index, changeType)
