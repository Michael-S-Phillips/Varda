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
            # Fix coordinate transformation - check if we need absolute coords
            pos = self._getCorrectCoordinates(ev.scenePos())

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
            pos = self._getCorrectCoordinates(ev.scenePos())

            if self.isDrawing:
                if self.mode == ROIMode.FREEHAND:
                    if self.pts is not None:
                        self.pts[0].append(pos.x())
                        self.pts[1].append(pos.y())
                        self.updatePath()

                elif self.mode == ROIMode.RECTANGLE or self.mode == ROIMode.ELLIPSE:
                    if self.startPoint is not None:
                        # Update rectangle from start point to current position
                        self.rect = QRectF(self.startPoint, pos).normalized()

                elif self.mode == ROIMode.POLYGON:
                    # Update temp point for preview line
                    self.tempPoint = pos

                # Force a visual update
                self.prepareGeometryChange()
                self.update()

            return True

        return False

    def _getCorrectCoordinates(self, scenePos):
        """
        Get the correct coordinates based on the view type.
        """
        # Map scene position to item coordinates
        itemPos = self.mapFromScene(scenePos)
        
        # Get view type (default to context if not set)
        view_type = getattr(self, 'view_type', 'context')
        
        if view_type == "context":
            # Context view coordinates are already absolute
            return itemPos
        
        elif view_type == "main":
            # Main view: ROI is parented to mainImage, so coordinates are relative to mainImage
            # No additional transformation needed - PyQtGraph handles it via parent-child relationship
            return itemPos
        
        elif view_type == "zoom":
            # Zoom view: ROI is parented to zoomImage
            # Use getAbsoluteCoords only for zoom since zoomImage has the region transform
            if (self.targetImageItem and 
                hasattr(self.targetImageItem, 'getAbsoluteCoords')):
                return self.targetImageItem.getAbsoluteCoords(itemPos)
            else:
                return itemPos
        
        # Default case
        return itemPos
    
    def _convertMainViewToAbsolute(self, itemPos):
        """Convert main view coordinates to absolute coordinates"""
        try:
            # Find the raster view through the scene
            scene = self.scene()
            if scene and hasattr(scene, 'views') and len(scene.views()) > 0:
                # Look for raster view in scene items
                raster_view = None
                for item in scene.items():
                    if hasattr(item, 'raster_view'):
                        raster_view = item.raster_view
                        break
                
                # Try to find raster view through parent relationships
                if not raster_view:
                    current = self.parentItem()
                    while current and not raster_view:
                        if hasattr(current, 'raster_view'):
                            raster_view = current.raster_view
                            break
                        # Check if current item's scene has a raster_view reference
                        if hasattr(current, 'scene') and hasattr(current.scene(), 'raster_view'):
                            raster_view = current.scene().raster_view
                            break
                        current = current.parentItem()
                
                # Get context ROI offset
                if raster_view and hasattr(raster_view, 'contextROI') and raster_view.contextROI:
                    offset_x = raster_view.contextROI.pos().x()
                    offset_y = raster_view.contextROI.pos().y()
                    
                    abs_x = itemPos.x() + offset_x
                    abs_y = itemPos.y() + offset_y
                    return QPointF(abs_x, abs_y)
            
            # Fallback: return original coordinates
            return itemPos
            
        except Exception as e:
            logger.error(f"Error converting main view coordinates: {e}")
            return itemPos

    def _convertZoomViewToAbsolute(self, itemPos):
        """Convert zoom view coordinates to absolute coordinates"""
        try:
            # Find the raster view through the scene (similar to main view)
            scene = self.scene()
            if scene and hasattr(scene, 'views') and len(scene.views()) > 0:
                raster_view = None
                for item in scene.items():
                    if hasattr(item, 'raster_view'):
                        raster_view = item.raster_view
                        break
                
                if not raster_view:
                    current = self.parentItem()
                    while current and not raster_view:
                        if hasattr(current, 'raster_view'):
                            raster_view = current.raster_view
                            break
                        current = current.parentItem()
                
                # Get both context and main ROI offsets for zoom view
                if (raster_view and 
                    hasattr(raster_view, 'contextROI') and raster_view.contextROI and
                    hasattr(raster_view, 'mainROI') and raster_view.mainROI):
                    
                    context_offset_x = raster_view.contextROI.pos().x()
                    context_offset_y = raster_view.contextROI.pos().y()
                    main_offset_x = raster_view.mainROI.pos().x()
                    main_offset_y = raster_view.mainROI.pos().y()
                    
                    abs_x = itemPos.x() + context_offset_x + main_offset_x
                    abs_y = itemPos.y() + context_offset_y + main_offset_y
                    return QPointF(abs_x, abs_y)
            
            # Fallback: return original coordinates
            return itemPos
            
        except Exception as e:
            logger.error(f"Error converting zoom view coordinates: {e}")
            return itemPos
    
    def updatePath(self):
        """Update the path from current points and trigger visual update"""
        if self.pts is None or len(self.pts[0]) < 2:
            return
            
        # Prepare for geometry change
        self.prepareGeometryChange()
        
        # Create path from points
        from PyQt6.QtGui import QPainterPath
        self.path = QPainterPath()
        
        # Start the path at the first point
        self.path.moveTo(self.pts[0][0], self.pts[1][0])
        
        # Add lines to subsequent points
        for i in range(1, len(self.pts[0])):
            self.path.lineTo(self.pts[0][i], self.pts[1][i])
        
        # Close the path if we have enough points and it's not polygon mode during drawing
        if len(self.pts[0]) >= 3 and not (self.mode == ROIMode.POLYGON and self.isDrawing):
            self.path.closeSubpath()
        
        # Force immediate visual update
        self.update()

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

        # Transform coordinates to absolute image coordinates based on view type
        absolute_points = self._transformToAbsoluteCoordinates(self.pts)

        # Calculate geo coordinates if transform is available
        geoPoints = None
        if self.geoTransform is not None and absolute_points is not None:
            geoPoints = self._pixelToGeoFromAbsolute(absolute_points)

        # Emit the completed ROI with absolute coordinates
        if absolute_points is not None and len(absolute_points[0]) >= 3:
            result = {
                "points": absolute_points,  # Now using absolute coordinates
                "geo_points": geoPoints,
                "image_index": self.imageIndex,
                "color": self.color,
                "mode": self.mode,
                "view_type": getattr(self, 'view_type', 'context')
            }
            self.sigDrawingComplete.emit(result)
        else:
            self.sigDrawingCanceled.emit()

    def _transformToAbsoluteCoordinates(self, points):
        """Transform coordinates from view-specific to absolute image coordinates"""
        if points is None:
            return None
            
        view_type = getattr(self, 'view_type', 'context')
        
        if view_type == "context":
            # Context coordinates are already absolute
            return points
        
        elif view_type == "main":
            # For main view, we need to add the contextROI offset
            try:
                # Find the raster view to get contextROI position
                raster_view = self._findRasterView()
                
                if raster_view and hasattr(raster_view, 'contextROI') and raster_view.contextROI:
                    offset_x = raster_view.contextROI.pos().x()
                    offset_y = raster_view.contextROI.pos().y()
                    
                    abs_x = [x + offset_x for x in points[0]]
                    abs_y = [y + offset_y for y in points[1]]
                    return [abs_x, abs_y]
            
            except Exception as e:
                logger.error(f"Error transforming main view coordinates: {e}")
            
            # Fallback to original points
            return points
        
        elif view_type == "zoom":
            # For zoom view, coordinates should already be transformed by getAbsoluteCoords
            # But if they're not, apply the full transformation
            try:
                raster_view = self._findRasterView()
                
                if (raster_view and 
                    hasattr(raster_view, 'contextROI') and raster_view.contextROI and
                    hasattr(raster_view, 'mainROI') and raster_view.mainROI):
                    
                    context_offset_x = raster_view.contextROI.pos().x()
                    context_offset_y = raster_view.contextROI.pos().y()
                    main_offset_x = raster_view.mainROI.pos().x()
                    main_offset_y = raster_view.mainROI.pos().y()
                    
                    abs_x = [x + context_offset_x + main_offset_x for x in points[0]]
                    abs_y = [y + context_offset_y + main_offset_y for y in points[1]]
                    return [abs_x, abs_y]
            
            except Exception as e:
                logger.error(f"Error transforming zoom view coordinates: {e}")
            
            # Fallback to original points
            return points
        
        # Default case
        return points
    
    def _findRasterView(self):
        """Find the raster view instance through various means"""
        # Method 1: Check if we have a direct reference
        if hasattr(self, 'raster_view'):
            return self.raster_view
        return None
    
    def _pixelToGeoFromAbsolute(self, absolute_points):
        """Convert absolute pixel coordinates to geographic coordinates"""
        if self.geoTransform is None or absolute_points is None:
            return None

        try:
            import rasterio.transform

            # Convert points using the geotransform
            geo_x, geo_y = [], []
            for i in range(len(absolute_points[0])):
                x, y = absolute_points[0][i], absolute_points[1][i]
                # Apply the transform
                geo_coord = rasterio.transform.xy(self.geoTransform, y, x)
                geo_x.append(geo_coord[0])
                geo_y.append(geo_coord[1])

            return [geo_x, geo_y]
        except Exception as e:
            logger.error(f"Error converting to geo coordinates: {e}")
            return None
        
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

        # Draw the main path/shape
        if self.path is not None:
            # Draw the filled path
            p.setPen(self.pen)
            p.fillPath(self.path, self.brush)
            p.drawPath(self.path)

        # Draw rectangle/ellipse for those modes
        elif self.rect is not None:
            if self.mode == ROIMode.RECTANGLE:
                p.setPen(self.pen)
                p.setBrush(self.brush)
                p.drawRect(self.rect)
            elif self.mode == ROIMode.ELLIPSE:
                p.setPen(self.pen)
                p.setBrush(self.brush)
                p.drawEllipse(self.rect)

        # Special handling for polygon mode during drawing
        if self.mode == ROIMode.POLYGON and self.isDrawing and self.pts is not None:
            # Draw points as small circles
            point_pen = pg.mkPen("yellow", width=2)
            point_brush = pg.mkBrush("yellow")
            p.setPen(point_pen)
            p.setBrush(point_brush)
            
            for i in range(len(self.pts[0])):
                p.drawEllipse(QPointF(self.pts[0][i], self.pts[1][i]), 3, 3)

            # Draw line to temp point if it exists
            if self.tempPoint is not None and len(self.pts[0]) > 0:
                temp_pen = pg.mkPen("yellow", width=2, style=Qt.PenStyle.DashLine)
                p.setPen(temp_pen)
                p.drawLine(
                    QPointF(self.pts[0][-1], self.pts[1][-1]), self.tempPoint
                )

    def getLinePts(self):
        """Get the ROI points as a tuple of arrays ([x points], [y points])"""
        return self.pts
