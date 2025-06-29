# third-party imports
from typing import override

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF, QRect, QPoint

from varda.app.services import image_utils
from varda.core.entities import Image, Band, Stretch


class ImageRegionItem(pg.ImageItem):
    """
    Custom ImageItem that supports only displaying a region of the image,
    with a convenience method to get the absolute image coordinates.

    Currently, it only supports rectangular, axis aligned regions.
    This is because coordinates are calculated using as simple offset.
    We would need to use more complex affine transformations to support more complex regions.
    pyqtgraph has some stuff to support this, but idk if we even need to yet.
    """

    def __init__(self, image: Image, region: pg.ROI = None, **kwargs):
        super().__init__(**kwargs)
        # tried naming self.image but ImageItem already has an image property and so stuff broke lol
        self.imageEntity = image
        self.region = region
        self.imageRegion = None
        self.band = Band.createDefault()
        self.stretch = None

    def setRegion(self, region: pg.ROI, sourceImageItem: "ImageRegionItem"):
        """Set the region of interest for zooming."""
        self.imageRegion, coords = region.getArrayRegion(
            sourceImageItem.image, sourceImageItem, returnMappedCoords=True
        )
        self.region = region

        self._updateImage()

    def setBand(self, band: Band):
        """Set the band for the image item."""
        self.band = band
        self._updateImage()

    def setStretch(self, stretch: Stretch):
        """Set the stretch for the image item."""
        self.stretch = stretch
        self._updateImage()

    def _updateImage(self):
        """Set the image data for the item."""
        bandData = image_utils.getRasterFromBand(self.imageEntity, self.band)
        dataSubset = self.region.getArrayRegion(bandData, self)

        if self.stretch is None:
            # use auto-levels if no stretch is set
            self.setImage(dataSubset)
        else:
            self.setImage(dataSubset, levels=self.stretch.toList())

    def localToAbsolute(self, point: QPointF) -> QPointF:
        """Convert local zoomed coordinates to absolute image coordinates."""
        if self.region is None:
            return point
        # Calculate absolute coordinates based on the region
        abs_x = int(self.region.x() + point.x())
        abs_y = int(self.region.y() + point.y())
        return QPointF(abs_x, abs_y)

    def absoluteToLocal(self, point: QPointF) -> QPointF:
        """Convert absolute image coordinates to local zoomed coordinates."""
        if self.region is None:
            return point
        # Calculate local coordinates based on the region
        local_x = int(point.x() - self.region.x())
        local_y = int(point.y() - self.region.y())
        return QPointF(local_x, local_y)

    def getOffset(self) -> QPointF:
        """Get the offset of the image item."""
        if self.region is None:
            return QPointF(0, 0)
        return self.region.topLeft()
