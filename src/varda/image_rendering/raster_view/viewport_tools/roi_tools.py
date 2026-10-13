"""The Draw ROI tool.

One toolbar toggle turns ROI drawing on; it stays on, so shape after shape can
be drawn without going back to the toolbar. The kind of shape (freehand,
polygon, rectangle, ellipse) comes from ``setShape`` -- the workspace ties it
to the ROI manager's shape picker -- and each finished shape is emitted as
``{"geometry": Polygon, "roiType": ROIMode}``, in CRS coordinates when the
image is georeferenced, otherwise in pixels.

- Freehand: press, drag, release.
- Rectangle / ellipse: drag from corner to corner.
- Polygon: click each vertex; Enter or a double-click finishes, Backspace
  removes the last vertex.
- Cmd-drag (Ctrl-drag elsewhere) pans the view, even partway through a shape.
- Esc or a right-click drops the shape being drawn. With nothing in
  progress they fall through (a right-click still opens the view's menu).
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication
from shapely.geometry import Polygon as ShapelyPolygon

from varda.common.entities import ROIMode
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import (
        PolygonOverlayHandle,
    )

logger = logging.getLogger(__name__)

Point = tuple[float, float]
MIN_DRAG = 5  # px (view-local); smaller rectangles/ellipses are taken as clicks
DOUBLE_CLICK_SLOP = 2  # px (view-local) between the two clicks of a double-click


class _Sketch:
    """One shape being drawn. Methods return True once the shape is finished."""

    def __init__(self, start: Point):
        self.points: list[Point] = [start]

    def move(self, pos: Point) -> None:
        pass

    def release(self, pos: Point) -> bool:
        return False

    def press(self, pos: Point) -> bool:
        return False

    def key(self, key: int) -> bool:
        return False

    def outline(self) -> list[Point]:
        return self.points

    def isValid(self) -> bool:
        return len(self.outline()) >= 3


class _Freehand(_Sketch):
    def move(self, pos: Point) -> None:
        self.points.append(pos)

    def release(self, pos: Point) -> bool:
        return True


class _Box(_Sketch):
    """Rectangle or ellipse, dragged from one corner to the other."""

    def __init__(self, start: Point, ellipse: bool):
        super().__init__(start)
        self.start, self.end, self.ellipse = start, start, ellipse

    def move(self, pos: Point) -> None:
        self.end = pos

    def release(self, pos: Point) -> bool:
        self.end = pos
        return True

    def isValid(self) -> bool:
        return (
            abs(self.end[0] - self.start[0]) > MIN_DRAG
            and abs(self.end[1] - self.start[1]) > MIN_DRAG
        )

    def outline(self) -> list[Point]:
        (x0, y0), (x1, y1) = self.start, self.end
        if not self.ellipse:
            return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        theta = np.linspace(0, 2 * np.pi, 36, endpoint=False)
        cx, cy, rx, ry = (
            (x0 + x1) / 2,
            (y0 + y1) / 2,
            abs(x1 - x0) / 2,
            abs(y1 - y0) / 2,
        )
        return list(zip(cx + rx * np.cos(theta), cy + ry * np.sin(theta)))


class _Polygon(_Sketch):
    def __init__(self, start: Point):
        super().__init__(start)
        self.cursor: Point | None = None
        self._lastPress = time.monotonic()

    def move(self, pos: Point) -> None:
        self.cursor = pos

    def press(self, pos: Point) -> bool:
        """Add a vertex; a quick second click on the last vertex finishes."""
        now = time.monotonic()
        last = self.points[-1]
        doubleClick = (
            now - self._lastPress < QApplication.doubleClickInterval() / 1000
            and abs(pos[0] - last[0]) <= DOUBLE_CLICK_SLOP
            and abs(pos[1] - last[1]) <= DOUBLE_CLICK_SLOP
        )
        self._lastPress = now
        if doubleClick:
            return True
        self.points.append(pos)
        return False

    def key(self, key: int) -> bool:
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return True
        if key == Qt.Key.Key_Backspace and len(self.points) > 1:
            self.points.pop()
        return False

    def outline(self) -> list[Point]:
        return self.points if self.cursor is None else [*self.points, self.cursor]

    def isValid(self) -> bool:
        return len(self.points) >= 3

    def finished(self) -> list[Point]:
        return self.points


def _newSketch(shape: ROIMode, start: Point) -> _Sketch:
    if shape == ROIMode.POLYGON:
        return _Polygon(start)
    if shape in (ROIMode.RECTANGLE, ROIMode.ELLIPSE):
        return _Box(start, ellipse=shape == ROIMode.ELLIPSE)
    return _Freehand(start)


class ROIDrawTool(ViewportTool):
    toolName = "Draw ROI"
    toolDescription = (
        "Draw ROIs on the image, one after another. Pick the shape and the "
        "class in the ROI manager; Esc cancels the shape in progress."
    )
    toolCategory = "ROI Drawing"

    sigROIDrawingComplete = pyqtSignal(object)  # {"geometry", "roiType"}

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self.shape = ROIMode.FREEHAND
        self.imageEntity = viewport.imageEntity
        self._sketch: _Sketch | None = None
        self._preview: PolygonOverlayHandle | None = None

    def setShape(self, shape: ROIMode) -> None:
        self._cancel()
        self.shape = shape

    def isSketching(self) -> bool:
        return self._sketch is not None

    def activate(self):
        super().activate()
        self.showText(f"{self.toolName}: {self.toolDescription}", timeout=4000)

    def deactivate(self):
        self._cancel()
        super().deactivate()

    # --- input ---------------------------------------------------------------

    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.modifiers & Qt.KeyboardModifier.ControlModifier:
            return False  # Cmd/Ctrl-drag pans the view, even mid-shape
        pos = (event.localPos.x(), event.localPos.y())
        sketch = self._sketch
        if event.action == PointerAction.PRESS:
            if event.button == Qt.MouseButton.RightButton:
                return self._cancel()
            if event.button != Qt.MouseButton.LeftButton:
                return False
            if sketch is None:
                self._begin(pos)
            elif sketch.press(pos):
                self._finish()
            else:
                self._updatePreview()
            return True
        if sketch is None:
            return False
        if event.action == PointerAction.MOVE:
            sketch.move(pos)
            self._updatePreview()
            return True
        if (
            event.action == PointerAction.RELEASE
            and event.button == Qt.MouseButton.LeftButton
        ):
            if sketch.release(pos):
                self._finish()
            return True
        return False

    def onKeyEvent(self, event: KeyEvent) -> bool:
        if self._sketch is None:
            return False
        if event.key == Qt.Key.Key_Escape:
            return self._cancel()
        if self._sketch.key(event.key):
            self._finish()
        else:
            self._updatePreview()
        return True

    # --- drawing -------------------------------------------------------------

    def _begin(self, pos: Point) -> None:
        self._sketch = _newSketch(self.shape, pos)
        self._preview = self.viewport.addPolygonOverlay()
        self._updatePreview()

    def _updatePreview(self) -> None:
        if self._preview is None or self._sketch is None:
            return
        points = [QPointF(x, y) for x, y in self._sketch.outline()]
        if len(points) >= 3:
            points.append(points[0])
        self._preview.setPoints(points)

    def _cancel(self) -> bool:
        """Drop the shape in progress; False if there was none."""
        if self._sketch is None:
            return False
        self._sketch = None
        if self._preview is not None:
            self._preview.remove()
            self._preview = None
        return True

    def _finish(self) -> None:
        sketch = self._sketch
        assert sketch is not None
        outline = (
            sketch.finished() if isinstance(sketch, _Polygon) else sketch.outline()
        )
        valid = sketch.isValid()
        self._cancel()
        if valid:
            self.sigROIDrawingComplete.emit(
                {"geometry": self._geometry(outline), "roiType": self.shape}
            )

    def _geometry(self, outline: list[Point]) -> ShapelyPolygon:
        imagePoints = self.viewport.localToImage(outline)
        if self.imageEntity.hasGeospatialData:
            return ShapelyPolygon(
                [self.imageEntity.pixelToGeo(int(x), int(y)) for x, y in imagePoints]
            )
        return ShapelyPolygon(imagePoints)
