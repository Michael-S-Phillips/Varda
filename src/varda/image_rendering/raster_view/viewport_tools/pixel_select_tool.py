from __future__ import annotations

import logging
from typing import override, TYPE_CHECKING

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QPointF
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.plotting.plot import VardaPlotWidget

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import CrosshairHandle

logger = logging.getLogger(__name__)


class PixelSelectTool(ViewportTool):
    """Click+Ctrl to select a pixel; emits its integer coords upon mouse release."""

    sigPixelSelected = pyqtSignal(QPointF)

    # Tool metadata
    toolName = "Pixel Select"
    toolDescription = "Select individual pixels (Ctrl+Click)"
    toolCategory = "Selection"

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._crosshair: CrosshairHandle | None = None
        self.isDragging = False

        self.sigPixelSelected.connect(
            self.onPixelSelected
        )  # TODO: This is probably temp
        self.activate()

    def activate(self):
        super().activate()
        if self._crosshair is None:
            self._crosshair = self.viewport.addCrosshair()

    def deactivate(self):
        super().deactivate()
        if self._crosshair is not None:
            self._crosshair.remove()
            self._crosshair = None

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
        if self._crosshair is not None:
            self._crosshair.setVisible(True)

    def _hideCrosshairs(self):
        """Hide the crosshairs."""
        if self._crosshair is not None:
            self._crosshair.setVisible(False)

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
        if self._crosshair is not None:
            self._crosshair.setPos(centeredPos)
        if emitSignal:
            # get absolute image pos
            imagePos = pg.Point(self.viewport.imageItem.localToImage(pos))
            self.sigPixelSelected.emit(imagePos)

    def onPixelSelected(self, pixelCoords):
        # TODO: This is prob temp. Should somehow integrate with the more complex plotting system Michael was working on.
        # check that coordinates are within range
        x = int(pixelCoords.x())
        y = int(pixelCoords.y())
        image = self.viewport.imageEntity
        if x < 0 or y < 0 or x >= image.width or y >= image.height:
            logger.warning(f"Selected pixel ({x}, {y}) is out of image bounds")
            return

        wavelengths = (
            image.wavelengths
            if image.wavelengthsType is not str
            else np.arange(image.bandCount)
        )

        spectrum = image.getSpectrum(x, y)
        self.plotWidget = VardaPlotWidget()
        self.plotWidget.plot(
            wavelengths,
            spectrum.values,
            name=f"Pixel {spectrum.pixel_coordinates}",
        )
        self.plotWidget.show()
        # self.pixelPlot = PixelPlot()
        # self.pixelPlot.plot(self.viewport.imageEntity, pixelCoords)
