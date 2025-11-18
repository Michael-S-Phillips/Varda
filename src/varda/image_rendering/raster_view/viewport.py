import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from varda.common.entities import Image, Stretch, Band
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.protocols import Viewport
from varda.image_rendering.raster_view.image_region_item import (
    VardaImageItem,
)

logger = logging.getLogger(__name__)


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
        self._imageItem = VardaImageItem(self._imageRenderer)
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
        self._imageRenderer.sigShouldRefresh.connect(
            lambda: self.refresh() if self.selfUpdating else None
        )

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        self.selfUpdating = False

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        self.selfUpdating = True

    def setBand(self, band: Band, update=True):
        """Set the band for the image item."""
        self._imageItem.setBand(band, update)

    def setStretch(self, stretch: Stretch, update=True):
        """Set the stretch for the image item."""
        self._imageItem.setStretch(stretch, update)

    def refresh(self):
        """Refresh the image display with current settings."""
        self._imageItem.refresh()

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
    def imageEntity(self) -> Image:
        return self._imageRenderer.image

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        return self._vb

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        return self._gv.scene()
