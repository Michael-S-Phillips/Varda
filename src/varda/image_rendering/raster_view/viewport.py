import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from varda.common.entities import Image, Stretch, Band
from varda.features.components.protocols import Viewport, ViewportTool
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

    def __init__(self, imageEntity: Image, parent=None):
        super().__init__(parent)
        self.selfUpdating = True
        self._imageEntity = imageEntity

        self._imageItem = VardaImageItem(imageEntity)
        self._vb = pg.ViewBox(lockAspect=True, invertY=True)
        self._vb.setMouseEnabled(x=False, y=False)
        # self._vb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # self._imageItem = pg.ImageItem(
        #     image_utils.getRasterFromBand(self.imageEntity, self.band),
        #     levels=self.stretch.toList(),
        # )
        # self.imageItem = ImageRegionItem(image, autoLevels=False)

        self._vb.addItem(self.imageItem)
        self._vb.keyPressEvent = lambda event: None
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

    def setBand(self, band: Band, update=True):
        """Set the band for the image item."""
        self.imageItem.setBand(band, update)

    def setStretch(self, stretch: Stretch, update=True):
        """Set the stretch for the image item."""
        self.imageItem.setStretch(stretch, update)

    def refresh(self):
        """Refresh the image display with current settings."""
        self.imageItem.refresh()

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
