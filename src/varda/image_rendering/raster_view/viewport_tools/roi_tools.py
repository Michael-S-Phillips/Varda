"""
ROI Drawing Tools

Tool implementations for drawing different types of ROIs.
"""

import logging
from typing import List, Tuple

import numpy as np
from PyQt6.QtCore import pyqtSignal, QPointF, QRectF, Qt
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

import varda
from varda.common.entities import ROI
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.image_rendering.raster_view.protocols import Viewport
from varda.utilities import image_utils
from varda.rois.varda_roi import VardaROIItem

logger = logging.getLogger(__name__)


class ROIDrawingTool(ViewportTool):
    """
    Base class for all ROI drawing tools.

    This is an abstract class that provides common functionality for ROI drawing tools.
    Subclasses should define the ROI mode and other specific properties.
    """

    toolCategory = "ROI Drawing"

    # Signal emitted when ROI drawing is complete
    sigROIDrawingComplete = pyqtSignal(object)

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(viewport, parent)
        self.isDrawing = False
        self.points: List[Tuple[float, float]] = []
        self.imageEntity = viewport.imageEntity
        self.targetImageItem = viewport.imageItem
        self.roiEntity = None
        self.roiItem = None

    def activate(self):
        """Activate the ROI drawing tool."""
        super().activate()
        self.startDrawing()

    def deactivate(self):
        """Deactivate the ROI drawing tool."""
        if self.isDrawing:
            self.cancelDrawing()
        super().deactivate()

    def stopDrawing(self):
        """Reset the tool state"""
        self.isDrawing = False
        self.points = []
        self.viewport.removeItem(self.roiItem)
        self.roiItem = None
        self.roiEntity = None

    def startDrawing(self):
        """Start the drawing process"""
        self.isDrawing = True
        self.points = []  # Reset points

        # Create a new ROI entity
        self.roiEntity = ROI(sourceImageIndex=self.imageEntity.index)

        # Create a visual representation of the ROI
        self.roiItem = VardaROIItem(self.roiEntity)
        self.viewport.addItem(self.roiItem)

        self.showText(
            f"{self.toolDescription}. Esc to cancel.",
            pos=self.viewport.viewBox.scenePos(),
            anchor=(0, 0),
            timeout=3000,
        )

    def updateDrawing(self):
        """Update the drawing process"""
        self.roiEntity.points = np.array(self.points)
        self.roiItem.setROIData(self.roiEntity)

    def cancelDrawing(self):
        """Cancel the current drawing operation"""
        self.stopDrawing()

    def completeDrawing(self):
        """Complete the drawing and emit result"""
        if len(self.points) < 3:
            self.cancelDrawing()
            return

        # convert points to image space and store in the ROI entity
        self.roiEntity.points = np.array(
            self.viewport.imageItem.localToImage(self.points)
        )

        # Calculate geo coordinates if transform is available
        if self.imageEntity.metadata.hasGeospatialData:
            self.roiEntity.geoPoints = np.array(
                [
                    image_utils.transformPixelToGeoCoord(
                        self.imageEntity, int(px), int(py)
                    )
                    for px, py in self.roiEntity.points
                ]
            )
        else:
            self.roiEntity.geoPoints = None

        roiClone = self.roiEntity.clone()
        self.sigROIDrawingComplete.emit(roiClone)

        # TODO: Possibly change this if we decide on a different way to store ROIs
        varda.app.proj.roiManager.addROI(roiClone)
        self.stopDrawing()

    def keyPressEvent(self, event) -> bool:
        """Handle key press events"""
        if not self.isDrawing:
            return False

        if event.key() == Qt.Key.Key_Escape:
            self.cancelDrawing()
            return True

        return False

    def _mapPosition(self, pos: QPointF) -> QPointF:
        """Map scene position to image coordinates"""
        return self.targetImageItem.mapFromScene(pos)


class FreehandROITool(ROIDrawingTool):
    """Tool for drawing freehand ROIs."""

    toolName = "Freehand ROI"
    toolDescription = (
        "Draw a freehand ROI by clicking and dragging. Release to complete."
    )

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._mapPosition(event.scenePos())
            self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if self.points and len(self.points) > 0:
            pos = self._mapPosition(event.scenePos())
            self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True

        return False

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
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

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(viewport, parent)
        self.startPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _rectToPoints(self, rect: QRectF) -> List[Tuple[float, float]]:
        """Convert QRectF to point arrays"""
        x1, y1, x2, y2 = rect.getCoords()
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._mapPosition(event.scenePos())
            self.startPoint = pos
            self.points = self._rectToPoints(QRectF(pos, pos))
            self.updateDrawing()
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        pos = self._mapPosition(event.scenePos())
        rect = QRectF(self.startPoint, pos).normalized()
        self.points = self._rectToPoints(rect)
        self.updateDrawing()
        return True

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._mapPosition(event.scenePos())
            rect = QRectF(self.startPoint, pos).normalized()
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

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(viewport, parent)
        self.startPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _ellipseToPoints(
        self, rect: QRectF, num_points=36
    ) -> List[Tuple[float, float]]:
        """Convert QRectF to ellipse point arrays"""
        center_x = rect.center().x()
        center_y = rect.center().y()
        radius_x = rect.width() / 2
        radius_y = rect.height() / 2

        theta = np.linspace(0, 2 * np.pi, num_points)
        x = center_x + radius_x * np.cos(theta)
        y = center_y + radius_y * np.sin(theta)
        return [(x[i], y[i]) for i in range(num_points)]

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._mapPosition(event.scenePos())
            self.startPoint = pos
            self.points = self._ellipseToPoints(QRectF(pos, pos))
            self.updateDrawing()
            return True
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        pos = self._mapPosition(event.scenePos())
        rect = QRectF(self.startPoint, pos).normalized()
        self.points = self._ellipseToPoints(rect)
        self.updateDrawing()
        return True

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing or self.startPoint is None:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            pos = self._mapPosition(event.scenePos())
            rect = QRectF(self.startPoint, pos).normalized()
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

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(viewport, parent)
        self.tempPoint = None

    def startDrawing(self):
        super().startDrawing()
        self.tempPoint = None

    def completeDrawing(self):
        """override to remove the temporary point if it exists"""
        if self.tempPoint is not None:
            self.points.remove(self.tempPoint)
            self.tempPoint = None
        super().completeDrawing()

    def keyPressEvent(self, event) -> bool:
        if not self.isDrawing:
            return False

        if event.key() == Qt.Key.Key_Escape:
            self.cancelDrawing()
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.tempPoint is not None:
                # If there's a temp point, remove it before completing
                self.points.remove(self.tempPoint)
                self.tempPoint = None
            if len(self.points) >= 3:
                self.completeDrawing()
            return True
        if event.key() == Qt.Key.Key_Backspace:
            if len(self.points) > 0:
                if self.tempPoint is not None:
                    self.points.remove(self.tempPoint)
                    self.tempPoint = None
                # remove the last point
                self.points.pop()
                self.updateDrawing()
            return True

        return False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            if self.tempPoint is not None:
                # the point is already in the list. By setting tempPoint to None we "lock in" that point
                self.tempPoint = None
            else:
                pos = self._mapPosition(event.scenePos())
                self.points.append((pos.x(), pos.y()))
            self.updateDrawing()
            return True

        if event.button() == Qt.MouseButton.RightButton:
            self.cancelDrawing()
            return True

        return False

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        if event.button() == Qt.MouseButton.LeftButton:
            if len(self.points) >= 3:
                if self.tempPoint is not None:
                    self.points.remove(self.tempPoint)
                    self.tempPoint = None
                self.completeDrawing()
            return True

        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        if not self.isDrawing:
            return False

        pos = self._mapPosition(event.scenePos())

        # Remove previous temp point if it exists
        if self.tempPoint in self.points:
            self.points.remove(self.tempPoint)

        # Add new temp point for preview
        self.tempPoint = (pos.x(), pos.y())
        if len(self.points) > 0:
            self.points.append(self.tempPoint)
            self.updateDrawing()

        return True
