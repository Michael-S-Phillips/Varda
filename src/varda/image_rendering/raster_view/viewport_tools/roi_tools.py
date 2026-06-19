"""
ROI Drawing Tools

Tool implementations for drawing different types of ROIs.
Emits Shapely geometry + ROIMode on completion for the new ROI system.
"""

from __future__ import annotations

import logging
from typing import List, Tuple, TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import pyqtSignal, QPointF, QRectF, Qt
from shapely.geometry import Polygon as ShapelyPolygon

from varda.common.entities import ROIMode
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import (
        PolygonOverlayHandle,
    )

logger = logging.getLogger(__name__)


class ROIDrawingTool(ViewportTool):
    """
    Base class for all ROI drawing tools.

    On completion, emits ``sigROIDrawingComplete`` with a dict:
        {"geometry": ShapelyPolygon, "roiType": ROIMode}
    where geometry is in CRS coordinates (if georeferenced) or pixel coordinates.

    Pointer events arrive with `localPos` already in viewport-local coordinates,
    so drawing accumulates local points and converts to image/CRS coordinates only
    on completion.
    """

    toolCategory = "ROI Drawing"

    # Emits dict with "geometry" (Shapely Polygon in pixel coords) and "roiType" (ROIMode)
    sigROIDrawingComplete = pyqtSignal(object)

    roiMode: ROIMode = ROIMode.FREEHAND  # Subclasses override

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self.isDrawing = False
        self.points: List[Tuple[float, float]] = []
        self.imageEntity = viewport.imageEntity
        self._preview: PolygonOverlayHandle | None = None

    def activate(self):
        super().activate()
        self.startDrawing()

    def deactivate(self):
        if self.isDrawing:
            self.cancelDrawing()
        super().deactivate()

    def stopDrawing(self):
        """Reset the tool state."""
        self.isDrawing = False
        self.points = []
        if self._preview is not None:
            self._preview.remove()
            self._preview = None

    def startDrawing(self):
        """Start the drawing process."""
        self.isDrawing = True
        self.points = []

        self._preview = self.viewport.addPolygonOverlay()

        self.showText(f"{self.toolDescription}. Esc to cancel.", timeout=3000)

    def updateDrawing(self):
        """Update the preview polygon from current points."""
        if self._preview is None:
            return
        points = [QPointF(x, y) for x, y in self.points]
        if len(self.points) >= 3:
            points.append(QPointF(*self.points[0]))  # Close polygon
        self._preview.setPoints(points)

    def cancelDrawing(self):
        self.stopDrawing()

    def completeDrawing(self):
        """Convert pixel points to Shapely Polygon and emit result."""
        if len(self.points) < 3:
            self.cancelDrawing()
            return

        # Convert viewport-local coordinates to image pixel coordinates
        imagePoints = self.viewport.localToImage(self.points)

        # Build Shapely polygon in pixel space
        pixelPolygon = ShapelyPolygon(imagePoints)

        # If the image is georeferenced, convert to CRS coordinates
        if self.imageEntity.hasGeospatialData:
            geoCoords = [
                self.imageEntity.pixelToGeo(int(px), int(py)) for px, py in imagePoints
            ]
            geometry = ShapelyPolygon(geoCoords)
        else:
            geometry = pixelPolygon

        self.sigROIDrawingComplete.emit(
            {
                "geometry": geometry,
                "roiType": self.roiMode,
            }
        )

        self.stopDrawing()
        self.sigCompleted.emit()

    # --- Input dispatch ---

    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.action == PointerAction.PRESS:
            return self._onPress(event)
        if event.action == PointerAction.MOVE:
            return self._onMove(event)
        if event.action == PointerAction.RELEASE:
            return self._onRelease(event)
        return False

    def _onPress(self, event: PointerEvent) -> bool:
        return False

    def _onMove(self, event: PointerEvent) -> bool:
        return False

    def _onRelease(self, event: PointerEvent) -> bool:
        return False

    def onKeyEvent(self, event: KeyEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.key == Qt.Key.Key_Escape:
            self.cancelDrawing()
            return True

        return False


class FreehandROITool(ROIDrawingTool):
    """Tool for drawing freehand ROIs."""

    toolName = "Freehand ROI"
    toolDescription = (
        "Draw a freehand ROI by clicking and dragging. Release to complete."
    )
    roiMode = ROIMode.FREEHAND

    def _onPress(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            pos = event.localPos
            self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True
        elif event.button == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def _onMove(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if self.points and len(self.points) > 0:
            pos = event.localPos
            self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True

        return False

    def _onRelease(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            if len(self.points) >= 3:
                self.completeDrawing()
            else:
                self.cancelDrawing()
            return True

        return False


class RectangleROITool(ROIDrawingTool):
    """Tool for drawing rectangular ROIs."""

    toolName = "Rectangle ROI"
    toolDescription = (
        "Draw a rectangular ROI by clicking and dragging. Release to complete."
    )
    roiMode = ROIMode.RECTANGLE

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self.startPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _rectToPoints(self, rect: QRectF) -> List[Tuple[float, float]]:
        x1, y1, x2, y2 = rect.getCoords()
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def _onPress(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            pos = event.localPos
            self.startPoint = pos
            self.points = self._rectToPoints(QRectF(pos, pos))
            self.updateDrawing()
            return True
        elif event.button == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def _onMove(self, event: PointerEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        rect = QRectF(self.startPoint, event.localPos).normalized()
        self.points = self._rectToPoints(rect)
        self.updateDrawing()
        return True

    def _onRelease(self, event: PointerEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            rect = QRectF(self.startPoint, event.localPos).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.points = self._rectToPoints(rect)
                self.completeDrawing()
            else:
                self.cancelDrawing()
            return True

        return False


class EllipseROITool(ROIDrawingTool):
    """Tool for drawing elliptical ROIs."""

    toolName = "Ellipse ROI"
    toolDescription = (
        "Draw an elliptical ROI by clicking and dragging. Release to complete."
    )
    roiMode = ROIMode.ELLIPSE

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self.startPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _ellipseToPoints(
        self, rect: QRectF, num_points=36
    ) -> List[Tuple[float, float]]:
        center_x = rect.center().x()
        center_y = rect.center().y()
        radius_x = rect.width() / 2
        radius_y = rect.height() / 2

        theta = np.linspace(0, 2 * np.pi, num_points)
        x = center_x + radius_x * np.cos(theta)
        y = center_y + radius_y * np.sin(theta)
        return [(x[i], y[i]) for i in range(num_points)]

    def _onPress(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            pos = event.localPos
            self.startPoint = pos
            self.points = self._ellipseToPoints(QRectF(pos, pos))
            self.updateDrawing()
            return True
        elif event.button == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def _onMove(self, event: PointerEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        rect = QRectF(self.startPoint, event.localPos).normalized()
        self.points = self._ellipseToPoints(rect)
        self.updateDrawing()
        return True

    def _onRelease(self, event: PointerEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            rect = QRectF(self.startPoint, event.localPos).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.points = self._ellipseToPoints(rect)
                self.completeDrawing()
            else:
                self.cancelDrawing()
            return True

        return False


class PolygonROITool(ROIDrawingTool):
    """Tool for drawing polygon ROIs."""

    toolName = "Polygon ROI"
    toolDescription = (
        "Draw a Polygon ROI by clicking to add points. Press Enter to complete."
    )
    roiMode = ROIMode.POLYGON

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self.tempPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.tempPoint = None

    def completeDrawing(self):
        if self.tempPoint is not None:
            self.points.remove(self.tempPoint)
            self.tempPoint = None
        super().completeDrawing()

    def onKeyEvent(self, event: KeyEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.key == Qt.Key.Key_Escape:
            self.cancelDrawing()
            return True
        if event.key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.tempPoint is not None:
                self.points.remove(self.tempPoint)
                self.tempPoint = None
            if len(self.points) >= 3:
                self.completeDrawing()
            return True
        if event.key == Qt.Key.Key_Backspace:
            if len(self.points) > 0:
                if self.tempPoint is not None:
                    self.points.remove(self.tempPoint)
                    self.tempPoint = None
                self.points.pop()
                self.updateDrawing()
            return True

        return False

    def _onPress(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button == Qt.MouseButton.LeftButton:
            if self.tempPoint is not None:
                self.tempPoint = None
            else:
                pos = event.localPos
                self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True

        if event.button == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def _onMove(self, event: PointerEvent) -> bool:
        if not self.isDrawing:
            return False

        pos = event.localPos

        if self.tempPoint in self.points:
            self.points.remove(self.tempPoint)

        self.tempPoint = (pos.x(), pos.y())
        if len(self.points) > 0:
            self.points.append(self.tempPoint)
            self.updateDrawing()

        return True
