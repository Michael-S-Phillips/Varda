import logging
from typing import override

from PyQt6.QtCore import Qt, pyqtSignal, QPointF
import pyqtgraph as pg
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.image_rendering.raster_view.protocols import Viewport
from varda.features.components.plotting.pixel_plot import PixelPlot

logger = logging.getLogger(__name__)


class PixelSelectTool(ViewportTool):
    """Click+Ctrl to select a pixel; emits its integer coords upon mouse release."""

    sigPixelSelected = pyqtSignal(QPointF)

    # Tool metadata
    toolName = "Pixel Select"
    toolDescription = "Select individual pixels (Ctrl+Click)"
    toolCategory = "Selection"

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(viewport, parent)
        self.targetImageItem = viewport.imageItem
        self.vCrosshair = pg.InfiniteLine(angle=90, movable=False, pen="r")
        self.hCrosshair = pg.InfiniteLine(angle=0, movable=False, pen="r")
        self.vCrosshair.hide()
        self.hCrosshair.hide()
        self.isDragging = False

        self.sigPixelSelected.connect(self.plotPixel)  # TODO: This is probably temp
        self.activate()

    def activate(self):
        super().activate()
        self.viewport.addItem(self.vCrosshair)
        self.viewport.addItem(self.hCrosshair)

    def deactivate(self):
        super().deactivate()
        self.viewport.removeItem(self.vCrosshair)
        self.viewport.removeItem(self.hCrosshair)

    @override
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse press events to start pixel selection."""
        if (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.isDragging = True
            self._updateCrosshair(event.pos(), emitSignal=False)
            self._showCrosshairs()
            return True
        return False

    @override
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse drag events to update crosshairs and emit pixel selection."""
        if self.isDragging:
            self._updateCrosshair(event.scenePos(), emitSignal=False)
            return True
        return False

    @override
    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        """Handle mouse release events to finalize pixel selection."""
        if self.isDragging and event.button() == Qt.MouseButton.LeftButton:
            self.isDragging = False
            self._updateCrosshair(event.scenePos())
            self._hideCrosshairs()
            return True
        return False

    def _showCrosshairs(self):
        """Show the crosshairs at the current mouse position."""
        if not self.vCrosshair.isVisible():
            self.vCrosshair.show()
        if not self.hCrosshair.isVisible():
            self.hCrosshair.show()

    def _hideCrosshairs(self):
        """Hide the crosshairs."""
        if self.vCrosshair.isVisible():
            self.vCrosshair.hide()
        if self.hCrosshair.isVisible():
            self.hCrosshair.hide()

    def _updateCrosshair(self, scenePos, emitSignal=True):
        """
        Update the position of the crosshairs based on the mouse position.
        This assumes that the position is already in image coordinates.
        """
        # Convert scene position to local coordinates in the image item
        pos = self.viewport.imageItem.mapFromScene(scenePos)
        # get the exact pixel coordinate
        quantizedPos = pg.Point(int(pos.x()), int(pos.y()))

        # apply a visual offset so the crosshairs are at the center of the pixel instead of the top left corner.
        centeredPos = quantizedPos + pg.Point(0.5, 0.5)
        self.hCrosshair.setPos(centeredPos)
        self.vCrosshair.setPos(centeredPos)
        if emitSignal:
            # get absolute image pos
            imagePos = pg.Point(self.viewport.imageItem.localToImage(pos))
            self.sigPixelSelected.emit(imagePos)

    def plotPixel(self, pixelCoords):
        # TODO: This is prob temp. Should somehow integrate with the more complex plotting system Michael was working on.
        self.pixelPlot = PixelPlot()
        self.pixelPlot.plot(self.viewport.imageEntity, pixelCoords)
