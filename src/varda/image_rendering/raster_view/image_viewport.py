from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np

from varda import log
from varda.common.entities import VardaRaster
from varda.image_rendering import ImageRenderer
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.protocols import Viewport
from varda.image_rendering.raster_view.image_region_item import (
    VardaImageItem,
)


class ViewportMeta(type(QWidget), type(Viewport)):
    pass


class ImageViewport(QWidget, Viewport, metaclass=ViewportMeta):
    """
    Generic image viewer: holds a single Viewbox with an ImageRegionItem, and helper methods
    """

    sigImageChanged = pyqtSignal()

    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.selfUpdating = True

        self._imageRenderer = imageRenderer
        self._imageItem: VardaImageItem = VardaImageItem(self._imageRenderer)

        self._overlayImageRenderer: ImageRenderer | None = None
        self._overlayImageItem: VardaImageItem | None = None

        self._vb = pg.ViewBox(lockAspect=True, invertY=True)
        self._vb.setMouseEnabled(x=False, y=False)

        self._vb.addItem(self._imageItem)
        self._vb.keyPressEvent = lambda event: None
        self._gv = pg.GraphicsView()
        self._gv.setCentralItem(self._vb)
        layout = QVBoxLayout(self)
        layout.addWidget(self._gv)
        self.setLayout(layout)

        self._imageItem.sigImageChanged.connect(self.sigImageChanged)
        self._imageRenderer.sigShouldRefresh.connect(self.autoRefresh)

    def overlayImage(self, overlayImageRenderer: ImageRenderer):
        """Overlay an image on top of the current image.
        It's possible that we may want to support multiple overlay images in the future, or overlay with different blending modes,
        but for now we'll just support one.
        """
        self._overlayImageRenderer = overlayImageRenderer
        if self._overlayImageItem is not None:
            log.info("An image is already overlayed. Replacing it with the new one.")
            self.removeOverlayImage()
        self._overlayImageItem = VardaImageItem(overlayImageRenderer)
        self._vb.addItem(self._overlayImageItem)

        overlayImageRenderer.sigShouldRefresh.connect(self.autoRefresh)

    def removeOverlayImage(self):
        """Remove the overlay image."""
        if self._overlayImageItem is not None:
            self._vb.removeItem(self._overlayImageItem)
            self._overlayImageItem = None
            self._overlayImageRenderer.sigShouldRefresh.disconnect(self.autoRefresh)
            self._overlayImageRenderer = None
        else:
            log.warning("No overlay image to remove.")

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        self.selfUpdating = False

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        self.selfUpdating = True

    def autoRefresh(self):
        if self.selfUpdating:
            self.refresh()

    def refresh(self):
        """Refresh the image display with current settings."""
        self._imageItem.refresh()
        if self._overlayImageItem is not None:
            self._overlayImageItem.refresh()

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray:
        """
        Convert full-image pixel coordinates to the viewport's local coordinates
        (since a viewport may be showing only an inner region of the image).
        """
        if not self.imageItem.isShowingRegion:
            return pixelCoords
        pointsList = [(float(c), float(r)) for c, r in pixelCoords]
        return np.array(self.imageItem.imageToLocal(pointsList))

    def addItem(self, item):
        """Add a graphics item to the viewport."""
        self._vb.addItem(item)

    def removeItem(self, item):
        """Remove a graphics item from the viewport."""
        self._vb.removeItem(item)

    def installTool(self, tool: ViewportTool):
        """Shortcut to install a tool's event filter on the imageItem."""
        self._imageItem.installEventFilter(tool)

    def removeTool(self, tool: ViewportTool):
        """Shortcut to remove a tool's event filter from the imageItem."""
        self._imageItem.removeEventFilter(tool)

    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""
        self.layout().addWidget(toolbar)

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        return self._imageItem

    @property
    def imageEntity(self) -> VardaRaster:
        return self._imageRenderer.image

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        return self._vb

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        return self._gv.scene()
