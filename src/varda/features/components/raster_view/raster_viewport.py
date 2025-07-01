from typing import Protocol

import numpy as np
from PyQt6.QtCore import pyqtSignal, QRectF, QPointF, QSizeF
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from varda.core.entities import Image, Stretch
from varda.features.components.raster_view.image_region_item import (
    VardaImageItem,
)
from varda.app.services import image_utils


class IViewport(Protocol):
    """
    Protocol for a viewport, which is a widget that displays image data.
    The purpose of this is to generalize an interface that can be used by controllers/tools/workflows.
    """

    sigImageChanged: pyqtSignal

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        ...

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        ...

    def setBand(self, band):
        """Set the band for the image item."""
        ...

    def setStretch(self, stretch):
        """Set the stretch for the image item."""
        ...

    def addItem(self, item):
        """Add a graphics item to the viewport"""
        ...

    def _attemptUpdate(self):
        """Update the image item with the current band and stretch."""
        ...

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        ...

    @property
    def imageEntity(self) -> Image:
        """Get the Image entity for this viewport."""
        ...

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        ...

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        ...


class ViewportMeta(type(QWidget), type(IViewport)):
    pass


class ImageViewport(QWidget, IViewport, metaclass=ViewportMeta):
    """
    Generic image viewer: holds a single Viewbox with an ImageRegionItem, and helper methods
    """

    sigImageChanged = pyqtSignal()

    def __init__(self, imageEntity: Image, parent=None):
        super().__init__(parent)
        self.selfUpdating = True
        self._imageEntity = imageEntity

        self._imageItem = VardaImageItem(imageEntity)

        self._vb = pg.ViewBox(lockAspect=True, invertY=True)
        self._vb.setMouseEnabled(x=False, y=False)

        # self._imageItem = pg.ImageItem(
        #     image_utils.getRasterFromBand(self.imageEntity, self.band),
        #     levels=self.stretch.toList(),
        # )
        # self.imageItem = ImageRegionItem(image, autoLevels=False)

        self._vb.addItem(self.imageItem)

        self._gv = pg.GraphicsView()
        self._gv.setCentralItem(self._vb)
        layout = QVBoxLayout(self)
        layout.addWidget(self._gv)
        self.setLayout(layout)

        self.imageItem.sigImageChanged.connect(self.sigImageChanged)

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        self.selfUpdating = False

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        self.selfUpdating = True

    def setBand(self, band, update=True):
        """Set the band for the image item."""
        self.imageItem.setBand(band, update)

    def setStretch(self, stretch, update=True):
        """Set the stretch for the image item."""
        self.imageItem.setStretch(stretch, update)

    def refresh(self):
        """Refresh the image display with current settings."""
        self.imageItem.refresh()

    def addItem(self, item):
        """Add a graphics item to the viewport."""
        self._vb.addItem(item)

    @property
    def imageEntity(self) -> Image:
        """Get the Image entity for this viewport."""
        return self._imageEntity

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        return self._imageItem

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        return self._vb

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        return self._gv.scene()
