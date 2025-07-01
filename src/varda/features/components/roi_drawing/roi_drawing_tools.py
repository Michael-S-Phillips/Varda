from typing import Tuple, List

from PyQt6.QtCore import pyqtSignal, QObject, QPointF, QRectF, Qt
import numpy as np
import logging
from dataclasses import dataclass

import pyqtgraph as pg

from varda.core.entities import ROI, ROIMode, Image
from varda.app.services import roi_utils, image_utils
from varda.features.components.raster_view.raster_viewport import IViewport

logger = logging.getLogger(__name__)


@dataclass
class ROIDrawingResult:
    """
    Data class to hold the result of a completed ROI drawing operation.
    """

    points: np.ndarray
    mode: ROIMode


class BaseROIDrawingTool(QObject):
    """
    Base class for ROI drawing tools.

    Each tool is an event filter that can be installed on viewports to capture
    drawing interactions. Tools only record points and emit signals - they don't
    handle display/rendering.
    """

    # Signals
    # We send the tool instance itself so that it can be removed from the scene after completing
    sigDrawingUpdated = pyqtSignal(object)  # Emits every time the points are updated
    sigDrawingComplete = pyqtSignal(object)  # Emits when the drawing is complete
    sigDrawingCanceled = pyqtSignal(object)  # Emits when drawing is canceled

    def __init__(self, viewport: IViewport, parent=None):
        super().__init__(parent)
        self.isDrawing = False
        self.points: List[Tuple[float, float]] = []
        self.viewport = viewport
        self.imageEntity = viewport.imageEntity
        self.targetImageItem = viewport.imageItem

        self.roiEntity = ROI(sourceImageIndex=self.imageEntity.index)

    def startDrawing(self):
        """Start the drawing process"""
        self.targetImageItem.installEventFilter(self)
        self.isDrawing = True
        self.points = []  # Reset points

    def updateDrawing(self):
        """drawing process has updated"""
        self.roiEntity.points = np.array(self.points)
        self.sigDrawingUpdated.emit(self)

    def cancelDrawing(self):
        """Cancel the current drawing operation"""
        self.targetImageItem.removeEventFilter(self)
        self.isDrawing = False
        self.points = []
        self.sigDrawingCanceled.emit(self)

    def completeDrawing(self):
        """Complete the drawing and emit result"""
        self.targetImageItem.removeEventFilter(self)

        if not self.points or len(self.points) < 3:
            self.cancelDrawing()
            return

        self.isDrawing = False

        # Calculate geo coordinates if transform is available
        if self.imageEntity.metadata.hasGeospatialData:
            geoPoints = [
                image_utils.transformPixelToGeoCoord(self.imageEntity, int(px), int(py))
                for px, py in self.points
            ]
        else:
            geoPoints = None

        self.roiEntity.points = np.array(self.points)
        self.roiEntity.geoPoints = np.array(geoPoints)
        self.sigDrawingComplete.emit(self)

    def getMode(self):
        """Return the drawing mode - to be implemented by subclasses"""
        raise NotImplementedError

    def eventFilter(self, obj, event):
        """Handle events - to be implemented by subclasses"""
        raise NotImplementedError

    def _mapPosition(self, scene_pos):
        """Map scene position to image coordinates"""
        # This might not be necessary if we're installing the event filter on the ImageItem itself
        # But unless it becomes a performance issue I'll leave it since its safer.
        return self.targetImageItem.mapFromScene(scene_pos)


class FreehandDrawingTool(BaseROIDrawingTool):
    """Tool for freehand ROI drawing"""

    def getMode(self):
        return ROIMode.FREEHAND

    def eventFilter(self, obj, event):
        if not self.isDrawing:
            return False

        # Handle key presses
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancelDrawing()
                return True

        # Handle mouse events
        elif event.type() == event.Type.GraphicsSceneMousePress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self._mapPosition(event.scenePos())
                self.points.append((pos.x(), pos.y()))
                self.updateDrawing()
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.cancelDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseMove:
            if self.points and len(self.points) > 0:
                pos = self._mapPosition(event.scenePos())
                self.points.append((pos.x(), pos.y()))
                self.updateDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                if len(self.points) >= 3:
                    self.completeDrawing()
                else:
                    self.cancelDrawing()
                return True

        return False


class RectangleDrawingTool(BaseROIDrawingTool):
    """Tool for rectangle ROI drawing"""

    def __init__(self, viewport: IViewport):
        self.startPoint = None
        super().__init__(viewport)

    def getMode(self):
        return ROIMode.RECTANGLE

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _rectToPoints(self, rect):
        """Convert QRectF to point arrays"""
        x1, y1, x2, y2 = rect.getCoords()
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]

    def eventFilter(self, obj, event):
        if not self.isDrawing:
            return False

        # Handle key presses
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancelDrawing()
                return True

        # Handle mouse events
        elif event.type() == event.Type.GraphicsSceneMousePress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self._mapPosition(event.scenePos())
                self.startPoint = pos
                self.points = self._rectToPoints(QRectF(pos, pos))
                self.updateDrawing()
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.cancelDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseMove:
            if self.startPoint is not None:
                pos = self._mapPosition(event.scenePos())
                rect = QRectF(self.startPoint, pos).normalized()
                self.points = self._rectToPoints(rect)
                self.updateDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseRelease:
            if (
                event.button() == Qt.MouseButton.LeftButton
                and self.startPoint is not None
            ):
                pos = self._mapPosition(event.scenePos())
                rect = QRectF(self.startPoint, pos).normalized()
                if rect.width() > 5 and rect.height() > 5:
                    self.points = self._rectToPoints(rect)
                    self.completeDrawing()
                else:
                    self.cancelDrawing()
                return True

        return False


class EllipseDrawingTool(BaseROIDrawingTool):
    """Tool for ellipse ROI drawing"""

    def __init__(self, viewport: IViewport):
        self.startPoint = None
        super().__init__(viewport)

    def getMode(self):
        return ROIMode.ELLIPSE

    def startDrawing(self):
        super().startDrawing()
        self.startPoint = None

    def _ellipseToPoints(self, rect, num_points=36):
        """Convert QRectF to ellipse point arrays"""
        center_x = rect.center().x()
        center_y = rect.center().y()
        radius_x = rect.width() / 2
        radius_y = rect.height() / 2

        theta = np.linspace(0, 2 * np.pi, num_points)
        x = center_x + radius_x * np.cos(theta)
        y = center_y + radius_y * np.sin(theta)
        return [(x[i], y[i]) for i in range(num_points)]

    def eventFilter(self, obj, event):
        if not self.isDrawing:
            return False

        # Handle key presses
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancelDrawing()
                return True

        # Handle mouse events
        elif event.type() == event.Type.GraphicsSceneMousePress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self._mapPosition(event.scenePos())
                self.startPoint = pos
                self.points = self._ellipseToPoints(QRectF(pos, pos))
                self.updateDrawing()
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.cancelDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseMove:
            if self.startPoint is not None:
                pos = self._mapPosition(event.scenePos())
                rect = QRectF(self.startPoint, pos).normalized()
                self.points = self._ellipseToPoints(rect)
                self.updateDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseRelease:
            if (
                event.button() == Qt.MouseButton.LeftButton
                and self.startPoint is not None
            ):
                pos = self._mapPosition(event.scenePos())
                rect = QRectF(self.startPoint, pos).normalized()
                if rect.width() > 5 and rect.height() > 5:
                    self.points = self._ellipseToPoints(rect)
                    self.completeDrawing()
                else:
                    self.cancelDrawing()
                return True

        return False


class PolygonDrawingTool(BaseROIDrawingTool):
    """Tool for polygon ROI drawing (click-by-click)"""

    def __init__(self, viewport: IViewport):
        self.tempPoint = None
        super().__init__(viewport)

    def getMode(self):
        return ROIMode.POLYGON

    def startDrawing(self):
        super().startDrawing()
        self.tempPoint = None

    def eventFilter(self, obj, event):
        if not self.isDrawing:
            return False

        # Handle key presses
        if event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.cancelDrawing()
                return True
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if len(self.points) >= 3:
                    self.completeDrawing()
                return True
            elif event.key() == Qt.Key.Key_Backspace:
                if len(self.points) > 0:
                    self.points.pop()
                    self.updateDrawing()
                return True

        # Handle mouse events
        elif event.type() == event.Type.GraphicsSceneMousePress:
            if event.button() == Qt.MouseButton.LeftButton:
                pos = self._mapPosition(event.scenePos())
                self.points.append((pos.x(), pos.y()))
                self.updateDrawing()
                return True
            elif event.button() == Qt.MouseButton.RightButton:
                self.cancelDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseDoubleClick:
            if event.button() == Qt.MouseButton.LeftButton:
                if len(self.points) >= 3:
                    self.completeDrawing()
                return True

        elif event.type() == event.Type.GraphicsSceneMouseMove:
            pos = self._mapPosition(event.scenePos())
            if self.tempPoint is not None:
                self.points.remove(self.tempPoint)

            self.tempPoint = (pos.x(), pos.y())
            # Emit current points with temp point for preview
            if len(self.points) > 0:
                self.points.append(self.tempPoint)
                self.updateDrawing()
            return True

        return False


class ROIDrawingObject(pg.GraphicsObject):
    """
    Class for interactive ROI drawing in different modes.

    Supports freehand drawing, rectangle, ellipse, and polygon drawing modes.
    Maps ROIs to image coordinates to maintain position during pan/zoom.
    """

    sigDrawingComplete = pyqtSignal(object)  # Emits ROI data when drawing is complete
    sigDrawingCanceled = pyqtSignal()  # Emits when drawing is canceled

    def __init__(self, color=None, mode=ROIMode.FREEHAND):
        pg.GraphicsObject.__init__(self)

        # Basic properties
        self.mode = mode
        self.color = (
            color if color else (0, 0, 255, 100)
        )  # default: semi-transparent blue

        self.pixel_points = []  # existing points
        self.geo_points = []  # new points

        self.imageIndex = None

        # Drawing state
        self.isDrawing = False
        self.pts = None
        self.path = None
        self.tempPoint = None  # For preview of next point
        self.rect = None  # For rectangle/ellipse modes
        self.startPoint = None  # For rectangle/ellipse modes

        # Line styling
        self.penWidth = 1
        self.pen = pg.mkPen(color=self.color[:3], width=self.penWidth)
        self.brush = pg.mkBrush(*self.color)
        self.hoverPen = pg.mkPen(
            color=(255, 255, 0), width=self.penWidth
        )  # Yellow highlight

        # Instructions displayed during drawing
        self.instructions = {
            ROIMode.FREEHAND: "Click and drag to draw freehand ROI. Release to complete.",
            ROIMode.RECTANGLE: "Click and drag to define rectangle. Release to complete.",
            ROIMode.ELLIPSE: "Click and drag to define ellipse. Release to complete.",
            ROIMode.POLYGON: "Click to add points. Double-click or press Enter to complete. Esc to cancel.",
        }

        self.instructionVisible = False
        self.instructionItem = pg.TextItem(
            text=self.instructions[self.mode], color=(255, 255, 255), anchor=(0, 0)
        )
        self.instructionItem.setVisible(False)

        # GeoTransform (if available from image metadata)
        self.geoTransform = None
        self.targetImageItem = None

    def setTargetImageItem(self, targetImageItem):
        """
        Set the target image item this ROI should be linked to.
        This is used to ensure the ROI stays anchored to image coordinates during pan/zoom.

        Args:
            targetItem: The image item this ROI should be anchored to
        """
        self.targetImageItem = targetImageItem
        self.setParentItem(targetImageItem)

    def setTransformGroup(self, targetItem):
        """
        Link this ROI to the transformation of the target item (usually the image).
        This ensures the ROI stays anchored to image coordinates when panning/zooming.

        Args:
            targetItem: The image item this ROI should be anchored to
        """
        if targetItem is None:
            return

        # Create a transform group if needed
        if not hasattr(self, "transformGroup"):
            from pyqtgraph import TransformGroup

            self.transformGroup = TransformGroup()
            self.setTransformGroup(self.transformGroup)

        # Link the ROI's transform to the target item's transform
        if hasattr(targetItem, "viewTransform"):
            self.transformGroup.setTransform(targetItem.viewTransform())

    def setGeoTransform(self, transform):
        """Set geotransform matrix for converting pixel coordinates to geo coordinates"""
        self.geoTransform = transform

    def setImageIndex(self, index):
        """Set the image index this ROI belongs to"""
        self.imageIndex = index

    def setMode(self, mode):
        """Change the ROI drawing mode"""
        self.mode = mode
        if self.instructionVisible:
            self.instructionItem.setText(self.instructions[self.mode])

    def setColor(self, color):
        """Set the ROI color"""
        self.color = color
        self.pen.setColor(pg.mkColor(color[:3]))
        self.brush = pg.mkBrush(*color)
        self.update()

    def draw(self):
        """
        Start the ROI drawing process.
        Creates a TextItem with instructions and installs an event filter.
        """
        self.isDrawing = True
        self.pts = None
        self.path = None
        self.rect = None
        self.startPoint = None

        # Add instruction to the parent scene if not already
        if not self.instructionVisible:
            scene = self.scene()
            if scene:
                scene.addItem(self.instructionItem)
                self.instructionItem.setPos(10, 10)  # Top-left corner
                self.instructionItem.setVisible(True)
                self.instructionVisible = True

        # Install event filter
        self.scene().installEventFilter(self)
        self.prepareGeometryChange()

    def eventFilter(self, obj, ev):
        """Handle user input events for ROI drawing"""
        # Handle key presses for canceling or completing
        if ev.type() == ev.Type.KeyPress:
            if ev.key() == Qt.Key.Key_Escape:
                self.cancelDrawing()
                return True
            elif ev.key() == Qt.Key.Key_Return or ev.key() == Qt.Key.Key_Enter:
                if (
                    self.mode == ROIMode.POLYGON
                    and self.pts is not None
                    and len(self.pts[0]) >= 3
                ):
                    self.completeDrawing()
                    return True
            elif ev.key() == Qt.Key.Key_Backspace:
                # Remove the last point in polygon mode
                if (
                    self.mode == ROIMode.POLYGON
                    and self.pts is not None
                    and len(self.pts[0]) > 0
                ):
                    self.pts[0].pop()
                    self.pts[1].pop()
                    self.updatePath()
                    return True
            return False

        # Mouse release events
        elif ev.type() == ev.Type.GraphicsSceneMouseRelease:
            if ev.button() == Qt.MouseButton.LeftButton:
                if self.mode == ROIMode.FREEHAND:
                    if self.pts is not None and len(self.pts[0]) >= 3:
                        self.completeDrawing()
                    else:
                        self.cancelDrawing()

                elif self.mode == ROIMode.RECTANGLE or self.mode == ROIMode.ELLIPSE:
                    if (
                        self.rect is not None
                        and self.rect.width() > 5
                        and self.rect.height() > 5
                    ):
                        # Convert rect to points
                        if self.mode == ROIMode.RECTANGLE:
                            self.convertRectToPoints()
                        else:  # ELLIPSE
                            self.convertEllipseToPoints()
                        self.completeDrawing()
                    else:
                        self.cancelDrawing()

                return True

        # Mouse press events
        if ev.type() == ev.Type.GraphicsSceneMousePress:
            pos = self.targetImageItem.localToAbsolute(self.mapFromScene(ev.scenePos()))

            if ev.button() == Qt.MouseButton.LeftButton:
                if self.mode == ROIMode.FREEHAND:
                    self.startPoint = pos
                    self.pts = [[pos.x()], [pos.y()]]
                    self.updatePath()

                elif self.mode == ROIMode.RECTANGLE or self.mode == ROIMode.ELLIPSE:
                    self.startPoint = pos
                    self.rect = QRectF(pos, pos)  # zero-size initial rect

                elif self.mode == ROIMode.POLYGON:
                    if self.pts is None:
                        self.pts = [[pos.x()], [pos.y()]]
                    else:
                        self.pts[0].append(pos.x())
                        self.pts[1].append(pos.y())
                    self.updatePath()

                    # If double-click, complete the polygon
                    if ev.type() == ev.Type.GraphicsSceneMouseDoubleClick:
                        if len(self.pts[0]) >= 3:
                            self.completeDrawing()

                return True

            # Right-click to cancel
            elif ev.button() == Qt.MouseButton.RightButton:
                self.cancelDrawing()
                return True

        # Mouse move events
        elif ev.type() == ev.Type.GraphicsSceneMouseMove:
            pos = self.targetImageItem.localToAbsolute(self.mapFromScene(ev.scenePos()))

            if self.isDrawing:
                if self.mode == ROIMode.FREEHAND and self.pts is not None:
                    # Add point to freehand path
                    self.pts[0].append(pos.x())
                    self.pts[1].append(pos.y())
                    self.updatePath()

                elif (
                    self.mode == ROIMode.RECTANGLE or self.mode == ROIMode.ELLIPSE
                ) and self.startPoint is not None:
                    # Update rectangle/ellipse size
                    self.rect = QRectF(self.startPoint, pos).normalized()
                    self.prepareGeometryChange()

                elif self.mode == ROIMode.POLYGON:
                    # Show preview of the next line segment
                    self.tempPoint = pos
                    self.prepareGeometryChange()

            return True

        return False

    def updatePath(self):
        """Update the path based on current points"""
        if self.pts is None or len(self.pts[0]) == 0:
            self.path = None
            return

        self.path = pg.arrayToQPath(np.array(self.pts[0]), np.array(self.pts[1]))

        # For polygon mode, don't close the path unless completed
        if self.mode != ROIMode.POLYGON or not self.isDrawing:
            self.path.closeSubpath()

        self.prepareGeometryChange()

    def convertRectToPoints(self):
        """Convert rectangle to point arrays"""
        if self.rect is None:
            return

        # Create points for the 4 corners
        x1, y1, x2, y2 = self.rect.getCoords()
        self.pts = [
            [x1, x2, x2, x1],  # x-coordinates
            [y1, y1, y2, y2],  # y-coordinates
        ]
        self.updatePath()

    def convertEllipseToPoints(self):
        """Convert ellipse to point arrays"""
        if self.rect is None:
            return

        # Create points along the ellipse
        centerX = self.rect.center().x()
        centerY = self.rect.center().y()
        radiusX = self.rect.width() / 2
        radiusY = self.rect.height() / 2

        # Generate 36 points (every 10 degrees)
        theta = np.linspace(0, 2 * np.pi, 36)
        x = centerX + radiusX * np.cos(theta)
        y = centerY + radiusY * np.sin(theta)

        self.pts = [x.tolist(), y.tolist()]
        self.updatePath()

    def completeDrawing(self):
        """Complete the ROI drawing and emit the result"""
        self.isDrawing = False

        # Close the path
        if self.path is not None:
            self.path.closeSubpath()

        # Clean up
        self.cleanup()

        # Calculate geo coordinates if transform is available
        geoPoints = None
        if self.geoTransform is not None and self.pts is not None:
            geoPoints = self.pixelToGeo()

        # Emit the completed ROI
        if self.pts is not None and len(self.pts[0]) >= 3:
            result = {
                "points": self.pts,
                "geo_points": geoPoints,
                "image_index": self.imageIndex,
                "color": self.color,
                "mode": self.mode,
            }
            self.sigDrawingComplete.emit(result)
        else:
            self.sigDrawingCanceled.emit()

    def cancelDrawing(self):
        """Cancel the current drawing operation"""
        self.isDrawing = False
        self.pts = None
        self.path = None
        self.rect = None
        self.startPoint = None
        self.tempPoint = None

        # Clean up
        self.cleanup()

        self.sigDrawingCanceled.emit()

    def cleanup(self):
        """Clean up resources after drawing is complete"""
        # Remove the instruction text
        if self.instructionVisible:
            self.scene().removeItem(self.instructionItem)
            self.instructionVisible = False

        # Remove event filter
        self.scene().removeEventFilter(self)

        self.prepareGeometryChange()

    def pixelToGeo(self):
        """Convert pixel coordinates to geographic coordinates using the geotransform"""
        if self.geoTransform is None or self.pts is None:
            return None

        try:
            import rasterio.transform

            # Convert points using the geotransform
            geo_x, geo_y = [], []
            for i in range(len(self.pts[0])):
                x, y = self.pts[0][i], self.pts[1][i]
                # Apply the transform
                geo_coord = rasterio.transform.xy(self.geoTransform, y, x)
                geo_x.append(geo_coord[0])
                geo_y.append(geo_coord[1])

            return [geo_x, geo_y]
        except Exception as e:
            logger.error(f"Error converting to geo coordinates: {e}")
            return None

    def boundingRect(self):
        """Return the bounding rectangle of the ROI"""
        if self.path is not None:
            return self.path.boundingRect()
        elif self.rect is not None:
            return self.rect
        elif self.pts is not None and len(self.pts[0]) > 0:
            # Calculate bounding rect from points
            min_x = min(self.pts[0])
            max_x = max(self.pts[0])
            min_y = min(self.pts[1])
            max_y = max(self.pts[1])
            return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)
        else:
            return QRectF()

    def paint(self, p, *args):
        """Paint the ROI on the graphic view"""
        p.setRenderHint(p.RenderHint.Antialiasing)

        if self.path is not None:
            # Draw the filled path
            p.setPen(self.pen)
            p.drawPath(self.path)
            p.fillPath(self.path, self.brush)

            # For polygon mode, show points
            if self.mode == ROIMode.POLYGON and self.isDrawing:
                for i in range(len(self.pts[0])):
                    p.setPen(pg.mkPen("y", width=2))
                    p.setBrush(pg.mkBrush("y"))
                    p.drawEllipse(QPointF(self.pts[0][i], self.pts[1][i]), 3, 3)

                # Draw line to temp point if it exists
                if self.tempPoint is not None and len(self.pts[0]) > 0:
                    p.setPen(pg.mkPen("y", width=2, style=Qt.PenStyle.DashLine))
                    p.drawLine(
                        QPointF(self.pts[0][-1], self.pts[1][-1]), self.tempPoint
                    )

        elif self.rect is not None:
            if self.mode == ROIMode.RECTANGLE:
                p.setPen(self.pen)
                p.setBrush(self.brush)
                p.drawRect(self.rect)
            elif self.mode == ROIMode.ELLIPSE:
                p.setPen(self.pen)
                p.setBrush(self.brush)
                p.drawEllipse(self.rect)

    def getLinePts(self):
        """Get the ROI points as a tuple of arrays ([x points], [y points])"""
        return self.pts

    def highlight(self, highlight=True):
        """Highlight the ROI by changing the pen color"""
        if highlight:
            self.pen.setColor(pg.mkColor("yellow"))
        else:
            self.pen.setColor(pg.mkColor(self.color[:3]))
        self.update()


__all__ = [
    "BaseROIDrawingTool",
    "FreehandDrawingTool",
    "RectangleDrawingTool",
    "EllipseDrawingTool",
    "PolygonDrawingTool",
    "ROIDrawingObject",
    "ROIDrawingResult",
]
