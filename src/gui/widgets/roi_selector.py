from PyQt6.QtCore import pyqtSignal, QPointF, QRectF, Qt, QPoint
import pyqtgraph as pg
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ROIMode:
    """Enum to define different ROI drawing modes"""

    FREEHAND = 0
    RECTANGLE = 1
    ELLIPSE = 2
    POLYGON = 3  # Click-by-click polygon


class ROISelector(pg.GraphicsObject):
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
        self.geo_points = []    # new points

        self.imageIndex = None

        # Drawing state
        self.isDrawing = False
        self.pts = None
        self.path = None
        self.tempPoint = None  # For preview of next point
        self.rect = None  # For rectangle/ellipse modes
        self.startPoint = None  # For rectangle/ellipse modes

        # Line styling
        self.penWidth = 2
        self.pen = pg.mkPen(color=self.color[:3], width=self.penWidth)
        self.brush = pg.mkBrush(*self.color)
        self.hoverPen = pg.mkPen(
            color=(255, 255, 0), width=self.penWidth + 1
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

        # Mouse press events
        if ev.type() == ev.Type.GraphicsSceneMousePress:
            pos = self.mapFromScene(ev.scenePos())

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
            pos = self.mapFromScene(ev.scenePos())

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
