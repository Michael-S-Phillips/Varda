# third-party imports
import logging

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform
from affine import Affine

from varda.features.components.rois.varda_roi import VardaROIItem
from varda.core import roi_utils, image_utils
from varda.common.entities import Image, Band, Stretch

logger = logging.getLogger(__name__)


def affine_to_qtransform(affine: Affine) -> QTransform:
    return QTransform(
        affine.a,
        affine.d,  # m11, m21
        affine.b,
        affine.e,  # m12, m22
        affine.c,
        affine.f,  # dx, dy
    )


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
        if band:
            self._band = band
        else:
            self._band = imageEntity.metadata.defaultBand
            logger.debug("Using default band: %s", self._band)
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

    def localToImage(self, point) -> QPointF:
        """Convert local coordinates to full image coordinates.
        Note that this does not protect against points outside the image bounds.
        """
        if not self._isShowingRegion:
            return point
        pointsList = []
        if isinstance(point, QPointF):
            pointsList.append((point.x(), point.y()))
        elif isinstance(point, tuple) and len(point) == 2:
            pointsList.append(point)
        elif isinstance(point, list | np.ndarray) and all(
            isinstance(p, tuple) and len(p) == 2 for p in point
        ):
            pointsList.extend(point)
        else:
            raise ValueError(
                "Invalid point format. Expected QPointF, tuple, or list of tuples."
            )
        converted = self._coordinateTransform.localToGlobal(pointsList)

        # return same type as input
        if isinstance(point, QPointF):
            return QPointF(pg.Point(converted[0]))
        return converted

    def imageToLocal(self, point) -> QPointF:
        """Convert full image coordinates to local coordinates.
        Note that this does not protect against points outside the image bounds.
        """
        if not self._isShowingRegion:
            return point

        pointsList = []
        if isinstance(point, QPointF):
            pointsList.append((point.x(), point.y()))
        elif isinstance(point, tuple) and len(point) == 2:
            pointsList.append(point)
        elif isinstance(point, list | np.ndarray) and all(
            isinstance(p, tuple) and len(p) == 2 for p in point
        ):
            pointsList.extend(point)
        else:
            raise ValueError(
                "Invalid point format. Expected QPointF, tuple, or list of tuples."
            )

        converted = self._coordinateTransform.globalToLocal(pointsList)
        return QPointF(pg.Point(converted))

    def getTransform(self):
        """Get the affine transform for the current region."""
        return affine_to_qtransform(self.imageEntity.metadata.transform)

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
            if isinstance(bandSlice, np.ma.MaskedArray):
                self._regionalData = bandSlice.filled(np.nan)
            else:
                self._regionalData = bandSlice
            # self._regionalData = bandSlice.filled(
            #     np.nan
            # )  # Fill NaNs to avoid display issues
            self._coordinateTransform = None

    @property
    def imageEntity(self) -> Image:
        """Get the underlying hyperspectral image entity."""
        return self._imageEntity

    @property
    def roi(self) -> VardaROIItem:
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
