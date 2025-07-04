# third-party imports
from typing import override, Optional
import logging

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF, QRect, QPoint

from varda.app.services import image_utils
from varda.app.services import roi_utils
from varda.app.services.roi_utils import RegionCoordinateTransform
from varda.core.entities import Image, Band, Stretch

logger = logging.getLogger(__name__)


class VardaImageItem(pg.ImageItem):
    """A modification of the pyqtgraph ImageItem. To support hyperspectral images and regional display from an ROI.

    Using Image, Stretch, and Band inputs, it handles the logic to generate an image suitable for display.
    It also can display a region of the image, and maps those local coordinates to absolute image coordinates.
    Being able to convert like this means we can draw ROIs on this item, and know where they are in the full image.
    """

    def __init__(
        self, imageEntity: Image, band: Band = None, stretch: Stretch = None, **kwargs
    ):
        super().__init__(**kwargs)

        self._imageEntity = imageEntity
        self._band = band or imageEntity.metadata.defaultBand
        self._stretch = stretch or Stretch.createDefault()

        # Region state
        self._backgroundImageItem = pg.ImageItem()
        self._backgroundImageItem.setZValue(-10)
        self._backgroundImageItem.setOpacity(0)

        self._roi = None
        self._regionalData = None
        self._coordinateTransform = None
        self._isShowingRegion = False

        # Update the display
        self.refresh()

    def setROI(self, roi: pg.ROI):
        """Set the region to display from the full image."""
        self._roi = roi
        self._isShowingRegion = True
        self.refresh()

    def clearROI(self):
        """Clear the region and show the full image."""
        self._roi = None
        self._coordinateTransform = None
        self._isShowingRegion = False
        self.refresh()

    def setBand(self, band: Band, update=True):
        """Set the band configuration."""
        self._band = band
        if update:
            self.refresh()

    def setStretch(self, stretch: Stretch, update=True):
        """Set the stretch configuration."""
        self._stretch = stretch
        if update:
            self.refresh()

    def refresh(self):
        """Refresh the image display with current settings."""
        self._updateImage()

    def localToImage(self, point: QPointF) -> QPointF:
        """Convert local coordinates to full image coordinates.
        Note that this does not protect against points outside the image bounds.
        """
        if not self._isShowingRegion:
            return point
        converted = self._coordinateTransform.localToGlobal((point.x(), point.y()))
        return QPointF(pg.Point(converted))

    def imageToLocal(self, point: QPointF) -> QPointF:
        """Convert full image coordinates to local coordinates.
        Note that this does not protect against points outside the image bounds.
        """
        if not self._isShowingRegion:
            return point
        converted = self._coordinateTransform.globalToLocal((point.x(), point.y()))
        return QPointF(pg.Point(converted))

    def _updateImage(self):
        """Update the displayed image data."""
        self._calculateRegionalData()
        self.setImage(self._regionalData, levels=self._stretch.toList())

    def _calculateRegionalData(self):
        """Get the current regional data being displayed."""
        bandSlice = image_utils.getRasterFromBand(self._imageEntity, self._band)

        if self._isShowingRegion:
            # get the region
            self._regionalData, self._coordinateTransform = (
                roi_utils.getMaskedArrayRegionSimple(
                    self._roi, bandSlice, returnTransform=True
                )
            )
            self._regionalData = self._regionalData.filled(
                np.nan
            )  # Fill NaNs to avoid display issues
        else:
            # Show full image
            self._regionalData = bandSlice.filled(
                np.nan
            )  # Fill NaNs to avoid display issues
            self._coordinateTransform = None

    @property
    def imageEntity(self) -> Image:
        """Get the underlying hyperspectral image entity."""
        return self._imageEntity

    @property
    def roi(self) -> roi_utils.VardaROI:
        """Get the current region being displayed."""
        return self._roi

    @property
    def isShowingRegion(self) -> bool:
        """Check if showing a region vs full image."""
        return self._isShowingRegion

    @property
    def coordinateTransform(self) -> np.ndarray:
        """Get the coordinate mapping array (if showing region)."""
        return self._coordinateTransform
