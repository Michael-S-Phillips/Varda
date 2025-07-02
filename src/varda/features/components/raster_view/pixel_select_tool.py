import logging

from PyQt6.QtCore import QObject, QEvent, Qt, pyqtSignal, QPointF
import pyqtgraph as pg
from PyQt6.QtGui import QPixmap

from varda.features.components.raster_view.raster_viewport import IViewport

logger = logging.getLogger(__name__)


class PixelSelectTool(QObject):

    sigPixelSelected = pyqtSignal(pg.Point)  # pg.Point is just a better QPointF

    def __init__(self, viewport: IViewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.targetImageItem = viewport.imageItem
        self.vCrosshair = pg.InfiniteLine(angle=90, movable=False, pen="r")
        self.hCrosshair = pg.InfiniteLine(angle=0, movable=False, pen="r")
        self.isDragging = False
        self.activate()

    def activate(self):
        self.targetImageItem.installEventFilter(self)
        self.viewport.addItem(self.vCrosshair)
        self.viewport.addItem(self.hCrosshair)

    def deactivate(self):
        self.targetImageItem.removeEventFilter(self)
        self.viewport.removeItem(self.vCrosshair)
        self.viewport.removeItem(self.hCrosshair)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.GraphicsSceneMousePress
            and event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.isDragging = True
            self._updateCrosshair(event)
            return True

        if event.type() == QEvent.Type.GraphicsSceneMouseMove and self.isDragging:
            self._updateCrosshair(event)
            return True

        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.isDragging = False
                self._updateCrosshair(event)
                return True
        return False

    def _updateCrosshair(self, event):
        # Get position. don't need to do any transformation because event filter is on the ImageItem directly.
        pos = event.pos()
        # get the exact pixel coordinate
        quantizedPos = pg.Point(int(pos.x()), int(pos.y()))

        # apply a visual offset so the crosshairs are at the center of the pixel instead of the top left corner.
        centeredPos = quantizedPos + pg.Point(0.5, 0.5)
        self.hCrosshair.setPos(centeredPos)
        self.vCrosshair.setPos(centeredPos)

        self.sigPixelSelected.emit(quantizedPos)
