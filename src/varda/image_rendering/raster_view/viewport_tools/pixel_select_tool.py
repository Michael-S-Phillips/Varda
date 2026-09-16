from __future__ import annotations

from typing import override, TYPE_CHECKING

import pyqtgraph as pg
from PyQt6.QtCore import Qt, pyqtSignal, QPointF

from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import PointerAction, PointerEvent

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import CrosshairHandle


class PixelSelectTool(ViewportTool):
    """Click+Ctrl to select a pixel; emits its image coords upon mouse release.

    The tool only reports the selection; the owning workspace decides what to
    do with it (e.g. plot the spectrum in its Pixel Spectra dock).
    """

    sigPixelSelected = pyqtSignal(QPointF)

    # Tool metadata
    toolName = "Pixel Select"
    toolDescription = "Select individual pixels (Ctrl+Click)"
    toolCategory = "Selection"

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._crosshair: CrosshairHandle | None = None
        self.isDragging = False
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
    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.action == PointerAction.PRESS:
            if (
                event.button == Qt.MouseButton.LeftButton
                and event.modifiers & Qt.KeyboardModifier.ControlModifier
            ):
                self.isDragging = True
                self._updateCrosshair(event, emitSignal=False)
                self._showCrosshairs()
                return True
            return False
        if event.action == PointerAction.MOVE:
            if self.isDragging:
                self._updateCrosshair(event, emitSignal=False)
                return True
            return False
        if event.action == PointerAction.RELEASE:
            if self.isDragging and event.button == Qt.MouseButton.LeftButton:
                self.isDragging = False
                self._updateCrosshair(event)
                self._hideCrosshairs()
                return True
            return False
        return False

    def _showCrosshairs(self):
        """Show the crosshairs at the current mouse position."""
        if self._crosshair is not None:
            self._crosshair.setVisible(True)

    def _hideCrosshairs(self):
        """Hide the crosshairs."""
        if self._crosshair is not None:
            self._crosshair.setVisible(False)

    def _updateCrosshair(self, event: PointerEvent, emitSignal=True):
        """Position the crosshairs at the pointer and optionally emit the pixel."""
        local = event.localPos
        # Quantize to a pixel, then offset to the pixel's centre for display.
        centeredPos = pg.Point(int(local.x()), int(local.y())) + pg.Point(0.5, 0.5)
        if self._crosshair is not None:
            self._crosshair.setPos(centeredPos)
        if emitSignal:
            self.sigPixelSelected.emit(event.imagePos)
