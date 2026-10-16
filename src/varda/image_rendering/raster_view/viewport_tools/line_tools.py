"""The Draw Line tool: straight lines, polylines and freehand lines.

Like Draw ROI, one toolbar toggle turns it on and it stays on. The kind of
line comes from a provider (the workspace ties it to the Lines manager), and
each finished line is emitted as (vertices, kind), the vertices in image
pixel coordinates (x = column, y = row).

- Straight: drag from one end to the other, or click both ends.
- Polyline: click each vertex; a double-click, a right-click or Enter
  finishes, Backspace removes the last vertex.
- Freehand: press, drag, release (the stroke is thinned to a polyline).
- Cmd-drag (Ctrl-drag elsewhere) pans the view, even partway through a line.
- Esc drops the line being drawn.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.lines.line_collection import LineKind
from varda.lines.profile import simplify

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import (
        PolylineOverlayHandle,
    )

Point = tuple[float, float]
MIN_DRAG = 4  # px (view-local); a shorter straight-line drag is a click
PREVIEW_COLOR = QColor(255, 210, 0)
FREEHAND_TOLERANCE = 0.75  # image pixels


class LineDrawTool(ViewportTool):
    toolName = "Draw Line"
    toolDescription = (
        "Draw lines for profiles, one after another. Pick straight, polyline or "
        "freehand in the Lines manager; Esc cancels the line in progress."
    )
    toolCategory = "Line Drawing"

    sigLineDrawn = pyqtSignal(object, object)  # vertices (n, 2) image px, LineKind

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._kind: Callable[[], LineKind] = lambda: LineKind.STRAIGHT
        self._points: list[Point] = []  # view-local
        self._cursor: Point | None = None
        self._dragging = False  # a straight line or freehand stroke in a drag
        self._preview: PolylineOverlayHandle | None = None

    def setKindProvider(self, provider: Callable[[], LineKind]) -> None:
        self._cancel()
        self._kind = provider

    def isDrawing(self) -> bool:
        return bool(self._points)

    def activate(self):
        super().activate()
        self.showText(f"{self.toolName}: {self.toolDescription}", timeout=4000)

    def deactivate(self):
        self._cancel()
        super().deactivate()

    # --- input ---------------------------------------------------------------

    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.modifiers & Qt.KeyboardModifier.ControlModifier:
            return False  # Cmd/Ctrl-drag pans the view, even mid-line
        pos = (event.localPos.x(), event.localPos.y())
        kind = self._kind()
        if event.action == PointerAction.DOUBLE_CLICK:
            if kind == LineKind.POLYLINE and self._points:
                self._finish()
            return bool(self._points)
        if event.action == PointerAction.PRESS:
            if event.button == Qt.MouseButton.RightButton:
                if kind == LineKind.POLYLINE and self._points:
                    self._finish()
                    return True
                return self._cancel()
            if event.button != Qt.MouseButton.LeftButton:
                return False
            if not self._points:
                self._points = [pos]
                self._dragging = kind != LineKind.POLYLINE
            elif kind == LineKind.STRAIGHT:
                self._points = [self._points[0], pos]  # the second click ends it
                self._finish()
                return True
            elif kind == LineKind.POLYLINE:
                self._points.append(pos)
            self._updatePreview()
            return True
        if not self._points:
            return False
        if event.action == PointerAction.MOVE:
            if kind == LineKind.FREEHAND and self._dragging:
                self._points.append(pos)
            else:
                self._cursor = pos
            self._updatePreview()
            return True
        if (
            event.action == PointerAction.RELEASE
            and event.button == Qt.MouseButton.LeftButton
        ):
            if kind == LineKind.FREEHAND and self._dragging:
                self._finish()
            elif kind == LineKind.STRAIGHT and self._dragging:
                self._dragging = False
                start = self._points[0]
                if np.hypot(pos[0] - start[0], pos[1] - start[1]) >= MIN_DRAG:
                    self._points = [start, pos]
                    self._finish()
                # else a click: the next click places the other end
            return True
        return False

    def onKeyEvent(self, event: KeyEvent) -> bool:
        if not self._points:
            return False
        if event.key == Qt.Key.Key_Escape:
            return self._cancel()
        if event.key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._finish()
            return True
        if event.key == Qt.Key.Key_Backspace and len(self._points) > 1:
            self._points.pop()
            self._updatePreview()
            return True
        return True

    # --- drawing -------------------------------------------------------------

    def _outline(self) -> list[Point]:
        if self._cursor is not None and self._kind() != LineKind.FREEHAND:
            return [*self._points, self._cursor]
        return self._points

    def _updatePreview(self) -> None:
        points = [QPointF(x, y) for x, y in self._outline()]
        if self._preview is None:
            self._preview = self.viewport.addPolylineOverlay(points, PREVIEW_COLOR)
        else:
            self._preview.setPoints(points)

    def _cancel(self) -> bool:
        """Drop the line in progress; False if there was none."""
        if not self._points:
            return False
        self._points, self._cursor, self._dragging = [], None, False
        if self._preview is not None:
            self._preview.remove()
            self._preview = None
        return True

    def _finish(self) -> None:
        kind = self._kind()
        local = list(self._points)
        self._cancel()
        vertices = np.asarray(self.viewport.localToImage(local), dtype=float)
        vertices = vertices.reshape(-1, 2)
        if kind == LineKind.FREEHAND:
            vertices = simplify(vertices, FREEHAND_TOLERANCE)
        # drop repeated points (a double-click places its vertex twice)
        keep = np.ones(len(vertices), bool)
        keep[1:] = np.any(np.abs(np.diff(vertices, axis=0)) > 1e-9, axis=1)
        vertices = vertices[keep]
        if len(vertices) >= 2:
            self.sigLineDrawn.emit(vertices, kind)
