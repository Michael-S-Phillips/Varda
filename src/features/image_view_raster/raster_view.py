import logging
import numpy as np
import rasterio
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEvent, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPolygonF
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg
from scipy.spatial import ConvexHull
from skimage.draw import polygon

from features.shared.selection_controls import StretchSelector, BandSelector
from features.image_view_roi.roi_drawing_manager import ROIDrawingManager
from gui.widgets.roi_selector import ROISelector
from core.entities.freehandROI import FreehandROI
from .raster_viewmodel import RasterViewModel

logger = logging.getLogger(__name__)


class RasterView(QWidget):
    """Main widget for displaying and interacting with raster images."""

    sigImageClicked = pyqtSignal(int, int)

    def __init__(self, viewmodel: RasterViewModel, parent=None):
        super().__init__(parent=parent)
        self.viewModel = viewmodel

        # Initialize image items and views
        self.mainImage = None
        self.contextImage = None
        self.zoomImage = None

        self.mainView = None
        self.contextView = None
        self.zoomView = None

        self.contextROI = None
        self.mainROI = None

        self.freehandROIs = []

        self.roiColors = [
            (255, 0, 0, 100),  # Red
            (0, 255, 0, 100),  # Green
            (0, 0, 255, 100),  # Blue
            (255, 255, 0, 100),  # Yellow
            (255, 0, 255, 100),  # Magenta
            (0, 255, 255, 100),  # Cyan
        ]
        self.colorIndex = 0
        self.highlighted_roi_index = None

        self.roiItems = {"main": [], "context": []}

        # Initialize the UI
        self._initUI()
        self._initROIS()
        self._connectSignals()

        # Log initial image information
        self._logImageInfo()

        # Draw any existing ROIs
        self._refresh_polygons()

    def _logImageInfo(self):
        """Log information about the loaded image."""
        try:
            image = self.viewModel.proj.getImage(self.viewModel.index)
            logger.debug(f"Image shape: {image.raster.shape}")
            logger.debug(
                f"Metadata wavelength shape: {image.metadata.wavelengths.shape}"
            )
            logger.debug(f"First few wavelengths: {image.metadata.wavelengths[:5]}")
            logger.debug(
                f"Wavelength range: {image.metadata.wavelengths.min():.2f} - {image.metadata.wavelengths.max():.2f} nm"
            )
        except Exception as e:
            logger.error(f"Error logging image info: {str(e)}")

    def _initUI(self):
        """Initialize the user interface components."""
        # Initialize Image Items
        self.mainImage = self._initImageItem()
        self.contextImage = self._initImageItem()
        self.zoomImage = self._initImageItem()
        # Initialize ROI drawing manager
        self.roi_drawing_manager = ROIDrawingManager(self, self.viewModel)
        # Initialize view boxes
        self.mainView = self._initViewBox("Main View", self.mainImage)
        self.contextView = self._initViewBox("Context View", self.contextImage)
        self.zoomView = self._initViewBox("Zoom View", self.zoomImage)

        # Initialize with consistent stretch values
        self.current_stretch_levels = None

        # Configure zoom view
        self.zoomView.setMouseEnabled(x=True, y=True)

        # Add crosshairs to zoom view
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen="r")
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen="r")
        self.zoomView.addItem(self.crosshair_v)
        self.zoomView.addItem(self.crosshair_h)

        # Connect zoom image click handler
        self.zoomImage.mouseClickEvent = self.zoomImageClicked

        # Build the layout
        self._buildLayout()

    def _buildLayout(self):
        """Build the widget layout."""
        # Create graphics views
        mainGraphicsView = pg.GraphicsView()
        mainGraphicsView.setCentralItem(self.mainView)

        contextGraphicsView = pg.GraphicsView()
        contextGraphicsView.setCentralItem(self.contextView)

        zoomGraphicsView = pg.GraphicsView()
        zoomGraphicsView.setCentralItem(self.zoomView)

        # Create splitters
        verticalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        verticalSplitter.addWidget(contextGraphicsView)
        verticalSplitter.addWidget(zoomGraphicsView)

        horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        horizontalSplitter.addWidget(mainGraphicsView)
        horizontalSplitter.addWidget(verticalSplitter)

        first_roi = ROISelector(None)
        first_roi.setImageIndex(self.viewModel.index)
        self.freehandROIs.append(first_roi)
        mainGraphicsView.addItem(self.freehandROIs[0])

        # Create main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(horizontalSplitter)
        self.setLayout(layout)

        # Add ROI toolbar if available
        if hasattr(self, "roi_drawing_manager"):
            roi_toolbar = self.roi_drawing_manager.getToolbar()
            if roi_toolbar:
                layout.addWidget(roi_toolbar)

    def zoomImageClicked(self, event):
        """Handle clicks on the zoom image."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Get click position in image coordinates
            pos = self.zoomImage.mapFromScene(event.scenePos())
            x, y = int(pos.x()), int(pos.y())

            # Convert to absolute image coordinates
            final_x, final_y = self._zoomCoordsToAbsolute(x, y)

            self._updateCrosshair(x, y)
            self.sigImageClicked.emit(final_x, final_y)

            # test geospatial info
            if self.viewModel.getImage().metadata.geoReferencer is not None:
                (
                    lon,
                    lat,
                ) = self.viewModel.getImage().metadata.geoReferencer.pixelToCoordinates(
                    final_x, final_y
                )
                noCRS_lon, noCRS_lat = rasterio.transform.xy(
                    self.viewModel.getImage().metadata.geoReferencer.transform,
                    final_x,
                    final_y,
                )
                (
                    new_x,
                    new_y,
                ) = self.viewModel.getImage().metadata.geoReferencer.coordinatesToPixel(
                    lon, lat
                )
                logger.debug(
                    f"Zoom Image clicked. \n   Pixel Coords: {final_x}, {final_y} \n   Geospatial Coords: {lon}, {lat}\n   Geospatial before applying CRS: {noCRS_lon}, {noCRS_lat}\n   Converted Geospatial Coords back to Pixel Coords: {new_x}, {new_y}"
                )
            else:
                logger.debug("Image does not contain geospatial info!")
        event.accept()

    def _zoomCoordsToAbsolute(self, xZoom, yZoom):
        """Transforms coordinates from the zoom view space into absolute image space"""
        final_x = int(self.contextROI.pos().x() + self.mainROI.pos().x() + xZoom)
        final_y = int(self.contextROI.pos().y() + self.mainROI.pos().y() + yZoom)

        image_size = self.viewModel.proj.getImage(self.viewModel.index).raster.shape
        if final_x in range(0, image_size[1]) and final_y in range(0, image_size[0]):
            return final_x, final_y
        else:
            raise IndexError(f"Selected coordinates are invalid: {final_x}, {final_y}")

    def _updateCrosshair(self, x, y):
        self.crosshair_v.setPos(x)
        self.crosshair_h.setPos(y)

    def _connectSignals(self):
        """Connect ROI signals."""
        if self.contextROI:
            self.contextROI.sigRegionChanged.connect(self._updateViews)
        if self.mainROI:
            self.mainROI.sigRegionChanged.connect(self._updateViews)

        # Make sure stretch changes are properly handled
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.viewModel.sigROIChanged.connect(self._refresh_polygons)

        # Add logging to better understand what's happening
        logger.debug("Connected signals in RasterView")

    def _initROIS(self):
        """Initialize Region of Interest elements."""
        self.clearROIs()

        # Initialize context ROI
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self.contextROI = self._getDefaultROI(self.contextImage)
        self.contextView.addItem(self.contextROI)

        # Initialize main ROI
        self._updateMainView()
        self.mainROI = self._getDefaultROI(self.mainImage)
        self.mainView.addItem(self.mainROI)

        # Update zoom view
        self._updateZoomView()

    def clearROIs(self):
        """Clear existing ROIs."""
        if self.contextROI is not None:
            self.contextView.removeItem(self.contextROI)
        if self.mainROI is not None:
            self.mainView.removeItem(self.mainROI)

    def _updateViews(self):
        """Update all views."""
        self._updateContextView()
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self._updateMainView()
        self._updateZoomView()
        self.draw_all_polygons()

    def _updateContextView(self):
        """Update the context view based on the current image."""

        self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
        logger.debug(
            f"Updating context image with new levels: {self.current_stretch_levels}"
        )
        rasterData = self.viewModel.getRasterFromBand()
        self.contextImage.setImage(rasterData, levels=self.current_stretch_levels)

        # Update the context image with the current raster data
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())

    def _updateMainView(self):
        """Update the main view based on context ROI."""
        if self.contextROI is None:
            return

        self._makeROISquare(self.contextROI)

        self.mainImage.setRegion(self.contextImage.image, self.contextROI, self.contextImage)

        if self.mainROI is not None:
            self.mainROI.maxBounds = self.mainImage.boundingRect()

    def _updateZoomView(self):
        """Update the zoom view based on main ROI."""
        if self.mainROI is None:
            return

        self._makeROISquare(self.mainROI)

        self.zoomImage.setRegion(self.mainImage.image, self.mainROI, self.mainImage)

    def _updateImageItem(self, imageItem, rasterData):
        """Update an image item with new raster data."""
        # If it's the context image, get fresh stretch values
        if imageItem == self.contextImage:
            self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
            logger.debug(
                f"Updating context image with new levels: {self.current_stretch_levels}"
            )

        # Always use the current stretch levels for consistency
        if self.current_stretch_levels is None:
            self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
            logger.debug(f"Initializing stretch levels: {self.current_stretch_levels}")
        imageItem.setImage(rasterData, levels=self.current_stretch_levels)

    def selectStretch(self, stretchIndex):
        """Select a new stretch to apply to the image."""
        self.viewModel.selectStretch(stretchIndex)

    def _onStretchChanged(self):
        """Handle stretch changes."""
        # Get the current stretch values directly from the view model
        stretch = self.viewModel.getSelectedStretch()
        levels = stretch.toList()

        # Update our cached stretch levels and log
        self.current_stretch_levels = levels
        logger.debug(
            f"RasterView received stretch change: {levels}, type: {type(levels[0][0])}"
        )

        # Update the image items with the new levels - explicitly convert to ensure correct types
        # Note: It's important that we pass the exact same levels object to all images
        self.mainImage.setLevels(levels)
        self.contextImage.setLevels(levels)
        self.zoomImage.setLevels(levels)

        # Force a redraw
        self.mainView.update()
        self.contextView.update()
        self.zoomView.update()

        logger.debug(f"After update, contextImage levels: {self.contextImage.levels}")

    def _onBandChanged(self):
        """Handle band changes."""
        self._updateViews()

    # def startDrawingROI(self):
    #     """Start the ROI drawing process."""
    #     if self.freehandROI:
    #         self.freehandROI.draw()

    def startNewROI(self):
        """Create and start a new ROI using the drawing manager"""
        self.roi_drawing_manager.startDrawingROI(self.mainImage)

    def highlightROI(self, roi_index):
        """Highlight a specific ROI by index"""
        self.highlighted_roi_index = roi_index
        self._refresh_polygons()

    def remove_polygons_from_display(self):
        """Remove all polygons from the display"""
        for item in self.roiItems["main"]:
            
            self.mainView.removeItem(item)
            
        for item in self.roiItems["context"]:
            self.contextView.removeItem(item)
        print("\n")
        for item in self.mainView.allChildren():
            if isinstance(item, ROISelector):
                self.mainView.removeItem(item)
                print(item)
        print("\n")


    def _refresh_polygons(self):
        """Redraw all ROI polygons"""
        print("here")
        self.remove_polygons_from_display()
        self.draw_all_polygons()

    # Update draw_all_polygons to support highlighting
    def draw_all_polygons(self):
        """Draw all ROIs with optional highlighting for the selected one"""
        # Get ROIs from the project
        self.remove_polygons_from_display()

        rois = self.viewModel.proj.get_rois_for_image(self.viewModel.index)
        if not rois:
            return

        for i, roi in enumerate(rois):
            # Get color and points from the ROI
            color = roi.color if hasattr(roi, "color") else (255, 0, 0, 128)
            highlighted = (
                hasattr(self, "highlighted_roi_index")
                and self.highlighted_roi_index == i
            )

            # Get points - handle different ROI formats
            if hasattr(roi, "points") and roi.points is not None:
                # FreehandROI style - points is [x_coords, y_coords]
                if isinstance(roi.points, list) and len(roi.points) == 2:
                    points = [(x, y) for x, y in zip(roi.points[0], roi.points[1])]
                else:
                    points = roi.points

                # Create a polygon with the points
                polygonForContext = pg.Qt.QtGui.QPolygonF()
                polygonForMain = pg.Qt.QtGui.QPolygonF()

                for x, y in zip(*points):
                    # add points to context polygon
                    polygonForContext.append(pg.Qt.QtCore.QPointF(x, y))
                    logger.debug("Adding point to polygon for context: ({}, {})".format(x, y))

                    # add points to main polygon, clamping to bounds
                    mainImageCoords = self.mainImage.getLocalCoords(QPointF(x, y))
                    polygonForMain.append(pg.Qt.QtCore.QPointF(mainImageCoords))
                    logger.debug("Adding point to polygon for main: ({}, {})".format(
                        mainImageCoords.x(),
                        mainImageCoords.y())
                    )

                # This clips the polygon to the bounds of the main image
                polygonForMain = polygonForMain.intersected(QPolygonF(self.mainImage.boundingRect()))

                # Create a polygon item with the color
                from PyQt6.QtGui import QPen, QBrush

                pen_width = 2
                if highlighted:
                    pen = QPen(QColor(255, 255, 0))  # Yellow for highlight
                    pen.setWidth(3)
                else:
                    pen = QPen(QColor(color[0], color[1], color[2]))
                    pen.setWidth(pen_width)

                brush = QBrush(
                    QColor(
                        color[0],
                        color[1],
                        color[2],
                        color[3] if len(color) >= 4 else 128,
                    )
                )
                contextPolygonItem = pg.Qt.QtWidgets.QGraphicsPolygonItem(polygonForContext)
                contextPolygonItem.setPen(pen)
                contextPolygonItem.setBrush(brush)
                self.contextView.addItem(contextPolygonItem)

                mainPolygonItem = pg.Qt.QtWidgets.QGraphicsPolygonItem(polygonForMain)
                mainPolygonItem.setPen(pen)
                mainPolygonItem.setBrush(brush)
                self.mainView.addItem(mainPolygonItem)

                # Store references to remove them later
                self.roiItems["main"].append(mainPolygonItem)
                self.roiItems["context"].append(contextPolygonItem)

    def closeEvent(self, event):
        """Clean up resources when the view is closed"""
        # Clean up ROI resources
        if hasattr(self, "roi_drawing_manager"):
            self.roi_drawing_manager.cleanupROIs()

        super().closeEvent(event)

    @staticmethod
    def _initImageItem():
        """Initialize a new image item."""
        return RasterView.ImageRegionItem(axisOrder="row-major", autoLevels=False, levels=(0, 1))

    @staticmethod
    def _initViewBox(name, imageItem):
        """Initialize a new view box."""
        viewBox = pg.ViewBox(name=name, lockAspect=True, invertY=True)
        viewBox.addItem(imageItem)

        # Enable mouse interaction for panning and zooming
        viewBox.setMouseEnabled(x=True, y=True)

        return viewBox

    @staticmethod
    def _getDefaultROI(imageItem):
        """Get default ROI for an image item."""
        imgRect = imageItem.boundingRect()
        center = imageItem.mapToParent(imgRect.center())
        startSize = (imgRect.width() / 4, imgRect.height() / 4)
        return pg.RectROI(center, startSize, pen=(0, 9), maxBounds=imgRect)

    @staticmethod
    def _makeROISquare(roi):
        """Make an ROI square shaped."""
        size = roi.size()
        minDim = min(size.x(), size.y())
        roi.setSize([minDim, minDim], update=False)
        handle = roi.handles[0]["item"]
        handle.setPos(minDim, minDim)

    class ImageRegionItem(pg.ImageItem):
        """
        Custom ImageItem that supports only displaying a region of the image,
        with a convenience method to get the absolute image coordinates.
        """

        def __init__(self, image=None, **kwargs):
            super().__init__(image=image, **kwargs)
            self.region = None

        def setRegion(self, image: pg.ImageItem, region: pg.ROI, sourceImageItem: pg.ImageItem):
            """Set the region of interest for zooming."""
            self.region = region
            rasterData = self.region.getArrayRegion(image, sourceImageItem)
            self.setImage(rasterData, autoLevels=False)

        def getAbsoluteCoords(self, point: QPointF):
            """Convert local zoomed coordinates to absolute image coordinates."""
            if self.region is None:
                return point
            # Calculate absolute coordinates based on the region
            abs_x = int(self.region.pos().x() + point.x())
            abs_y = int(self.region.pos().y() + point.y())
            return QPointF(abs_x, abs_y)

        def getLocalCoords(self, point: QPointF):
            """Convert absolute image coordinates to local zoomed coordinates."""
            if self.region is None:
                return point
            # Calculate local coordinates based on the region
            local_x = int(point.x() - self.region.pos().x())
            local_y = int(point.y() - self.region.pos().y())
            return QPointF(local_x, local_y)

        def getOffset(self):
            """Get the offset of the image item."""
            if self.region is None:
                return QtCore.QPointF(0, 0)
            return self.region.pos()