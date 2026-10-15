"""The Crop tool: drag a box on the image to crop it to that box.

The tool only reports the box (full-image pixels, snapped to whole pixels and
clamped to the image); the workspace makes the cropped image and adds it to
the project. Esc cancels a box in progress; Cmd-drag (Ctrl-drag elsewhere)
pans, as with the Draw ROI tool.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import PolygonOverlayHandle


def pixelBox(start: QPointF, end: QPointF, width: int, height: int) -> QRect:
    """The whole pixels a drag from ``start`` to ``end`` (image coordinates)
    covers, clamped to a ``width`` × ``height`` image (empty if outside)."""
    left = max(math.floor(min(start.x(), end.x())), 0)
    top = max(math.floor(min(start.y(), end.y())), 0)
    right = min(math.ceil(max(start.x(), end.x())), width)
    bottom = min(math.ceil(max(start.y(), end.y())), height)
    return QRect(left, top, max(right - left, 0), max(bottom - top, 0))


class CropTool(ViewportTool):
    toolName = "Crop"
    toolDescription = (
        "Drag a box to add a cropped copy of the image to the image list; Esc cancels."
    )
    toolCategory = "Selection"

    sigCropRequested = pyqtSignal(QRect)  # full-image pixels

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._start: QPointF | None = None  # image coords where the drag began
        self._localStart: QPointF | None = None
        self._preview: PolygonOverlayHandle | None = None

    def activate(self):
        super().activate()
        self.showText(f"{self.toolName}: {self.toolDescription}", timeout=4000)

    def deactivate(self):
        self._cancel()
        super().deactivate()

    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.modifiers & Qt.KeyboardModifier.ControlModifier:
            return False  # Cmd/Ctrl-drag pans
        if (
            event.action == PointerAction.PRESS
            and event.button == Qt.MouseButton.LeftButton
        ):
            self._start, self._localStart = event.imagePos, event.localPos
            self._preview = self.viewport.addPolygonOverlay(
                QColor(255, 220, 0), QColor(255, 220, 0, 40)
            )
            return True
        if self._start is None:
            return False
        if event.action == PointerAction.MOVE:
            self._updatePreview(event.localPos)
            return True
        if (
            event.action == PointerAction.RELEASE
            and event.button == Qt.MouseButton.LeftButton
        ):
            image = self.viewport.imageEntity
            box = pixelBox(self._start, event.imagePos, image.width, image.height)
            self._cancel()
            if box.width() >= 1 and box.height() >= 1:
                self.sigCropRequested.emit(box)
            return True
        return False

    def onKeyEvent(self, event: KeyEvent) -> bool:
        if self._start is not None and event.key == Qt.Key.Key_Escape:
            self._cancel()
            return True
        return False

    def _updatePreview(self, local: QPointF) -> None:
        if self._preview is None or self._localStart is None:
            return
        a, b = self._localStart, local
        self._preview.setPoints([a, QPointF(b.x(), a.y()), b, QPointF(a.x(), b.y()), a])

    def _cancel(self) -> None:
        self._start = self._localStart = None
        if self._preview is not None:
            self._preview.remove()
            self._preview = None
