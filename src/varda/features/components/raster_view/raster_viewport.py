from PyQt6.QtCore import pyqtSignal, QRectF, QPointF, QSizeF
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

from varda.core.entities import Image, Stretch
from varda.features.components.raster_view.image_region_item import ImageRegionItem
from varda.app.services import image_utils


class ImageViewport(QWidget):
    """
    Generic image viewer: holds a single Viewbox with an ImageRegionItem, and helper methods
    """

    def __init__(self, image: Image, parent=None):
        super().__init__(parent)
        self.selfUpdating = True
        self.image = image
        self.band = image.metadata.defaultBand
        self.stretch = Stretch.createDefault()

        self.vb = pg.ViewBox(lockAspect=True, invertY=True)
        self.vb.setMouseEnabled(x=False, y=False)

        self.imageItem = pg.ImageItem(
            image_utils.getRasterFromBand(self.image, self.band),
            levels=self.stretch.toList(),
        )
        # self.imageItem = ImageRegionItem(image, autoLevels=False)
        self.vb.addItem(self.imageItem)

        gv = pg.GraphicsView()
        gv.setCentralItem(self.vb)
        layout = QVBoxLayout(self)
        layout.addWidget(gv)
        self.setLayout(layout)

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        self.selfUpdating = False

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        self.selfUpdating = True
        self._attemptUpdate()

    def setBand(self, band):
        """Set the band for the image item."""
        self.band = band
        self._attemptUpdate()

    def setStretch(self, stretch):
        """Set the stretch for the image item."""
        self.stretch = stretch
        self._attemptUpdate()

    def _attemptUpdate(self):
        """Update the image item with the current band and stretch."""
        if self.selfUpdating:
            self.imageItem.setImage(
                image_utils.getRasterFromBand(self.image, self.band),
                levels=self.stretch.toList(),
            )
