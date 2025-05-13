import logging
import numpy as np
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEvent, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg
from scipy.spatial import ConvexHull
from skimage.draw import polygon

from features.shared.selection_controls import StretchSelector, BandSelector
from gui.widgets.ROI_selector import ROISelector
from core.entities.freehandROI import FreehandROI
from .raster_viewmodel import RasterViewModel

logger = logging.getLogger(__name__)


class PixelPlotWindow(QtWidgets.QMainWindow):
    """Separate window for displaying pixel spectrum plots."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Spectrum")
        # Set window flags to keep the window on top
        self.setWindowFlags(
            QtCore.Qt.WindowType.Window |
            QtCore.Qt.WindowType.WindowStaysOnTopHint
        )
        # Initialize the plot widget
        self.plot_widget = pg.PlotWidget(title="Pixel Spectrum")
        self.plot_widget.setMinimumSize(600, 300)
        self.plot_widget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plot_widget.addLegend()
        self.setCentralWidget(self.plot_widget)
        self.hide()  # Initially hidden

    def update_plot(self, wavelengths, spectral_data, coords):
        """Update the plot with new spectral data."""
        self.plot_widget.clear()
        logger.debug(f"Plotting spectrum for coordinates: {coords}")
        logger.debug(f"Wavelength range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")
        logger.debug(f"Spectral data range: {spectral_data.min():.2f} - {spectral_data.max():.2f}")

        self.plot_widget.plot(wavelengths, spectral_data, pen='y')
        self.plot_widget.setTitle(f"Pixel Spectrum at ({coords[0]}, {coords[1]})")
        if not self.isVisible():
            self.show()


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
        
        # Initialize the UI
        self._initUI()
        self._initROIS()
        self._connectSignals()
        
        # Log initial image information
        self._logImageInfo()

    def _logImageInfo(self):
        """Log information about the loaded image."""
        try:
            image = self.viewModel.proj.getImage(self.viewModel.index)
            logger.debug(f"Image shape: {image.raster.shape}")
            logger.debug(f"Metadata wavelength shape: {image.metadata.wavelengths.shape}")
            logger.debug(f"First few wavelengths: {image.metadata.wavelengths[:5]}")
            logger.debug(
                f"Wavelength range: {image.metadata.wavelengths.min():.2f} - {image.metadata.wavelengths.max():.2f} nm")
        except Exception as e:
            logger.error(f"Error logging image info: {str(e)}")

    def _initUI(self):
        """Initialize the user interface components."""
        # Initialize Image Items
        self.mainImage = self._initImageItem()
        self.contextImage = self._initImageItem()
        self.zoomImage = self._initImageItem()
        # Initialize view boxes
        self.mainView = self._initViewBox("Main View", self.mainImage)
        self.contextView = self._initViewBox("Context View", self.contextImage)
        self.zoomView = self._initViewBox("Zoom View", self.zoomImage)

        # Configure zoom view
        self.zoomView.setMouseEnabled(x=True, y=True)

        # Add crosshairs to zoom view
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen='r')
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen='r')
        self.zoomView.addItem(self.crosshair_v)
        self.zoomView.addItem(self.crosshair_h)

        # Connect zoom image click handler
        self.zoomImage.mouseClickEvent = self.zoomImageClicked

        # Initialize selectors
        self.stretchSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.index, self
        )
        self.bandSelector = BandSelector(
            self.viewModel.proj, self.viewModel.index, self
        )

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

        # Create selector layout
        selectorLayout = QtWidgets.QHBoxLayout()
        selectorLayout.addWidget(self.stretchSelector)
        selectorLayout.addWidget(self.bandSelector)

        first_roi = ROISelector(None)
        first_roi.setImageIndex(self.viewModel.index)
        self.freehandROIs.append(first_roi)
        mainGraphicsView.addItem(self.freehandROIs[0])

        # Create main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.addWidget(horizontalSplitter)
        self.setLayout(layout)

    def zoomImageClicked(self, event):
        """Handle clicks on the zoom image."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:

            # Get click position
            x, y = event.pos().x(), event.pos().y()
            final_x, final_y = self._zoomCoordsToAbsolute(x, y)

            self._updateCrosshair(x, y)
            self.sigImageClicked.emit(final_x, final_y)
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
            self.contextROI.sigRegionChanged.connect(self._updateMainView)
        if self.mainROI:
            self.mainROI.sigRegionChanged.connect(self._updateZoomView)

        self.freehandROIs[-1].sigDrawingComplete.connect(self._onROIDrawn)

        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)
        self.viewModel.sigBandChanged.connect(self._onBandChanged)


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
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self._updateMainView()

    def _updateMainView(self):
        """Update the main view based on context ROI."""
        if self.contextROI is None:
            return

        self._makeROISquare(self.contextROI)

        image = self.contextROI.getArrayRegion(
            self.contextImage.image, self.contextImage
        )
        self._updateImageItem(self.mainImage, image)

        if self.mainROI is not None:
            self.mainROI.maxBounds = self.mainImage.boundingRect()
            currentPos = self.mainROI.pos()
            self.mainROI.setPos(currentPos + QtCore.QPointF(1, 1))
            self.mainROI.setPos(currentPos)
        self._updateZoomView()

    def _updateZoomView(self):
        """Update the zoom view based on main ROI."""
        if self.mainROI is None:
            return

        self._makeROISquare(self.mainROI)

        image = self.mainROI.getArrayRegion(self.mainImage.image, self.mainImage)
        self._updateImageItem(self.zoomImage, image)

    def _updateImageItem(self, imageItem, rasterData):
        """Update an image item with new raster data."""
        levels = self.viewModel.getSelectedStretch().toList()
        imageItem.setImage(rasterData, levels=levels)

    def _onStretchChanged(self):
        """Handle stretch changes."""
        levels = self.viewModel.getSelectedStretch().toList()
        self.mainImage.setLevels(levels)
        self.contextImage.setLevels(levels)
        self.zoomImage.setLevels(levels)

    def _onBandChanged(self):
        """Handle band changes."""
        self._updateViews()
  
    # def startDrawingROI(self):
    #     """Start the ROI drawing process."""
    #     if self.freehandROI:
    #         self.freehandROI.draw()

    def startNewROI(self):
        """Create and start a new FreehandROI."""

        color = self.roiColors[self.colorIndex]
        self.colorIndex = (self.colorIndex + 1) % len(self.roiColors)

        new_roi = ROISelector(color)
        new_roi.setImageIndex(self.viewModel.index)
        self.freehandROIs.append(new_roi)
        self.mainView.addItem(new_roi)

        # Connect the new ROI's signal
        new_roi.sigDrawingComplete.connect(self._onROIDrawn)

        # Start drawing
        new_roi.draw()

    def extractArraySlice(self, roi: ROISelector):
        """
        Extract the raster data slice bounded by the given ROI points.
        
        Args:
            roi (ROISelector): The ROI object containing points.

        Returns:
            np.ndarray: The raster slice bounded by the ROI.
        """
        # Get raster data for the current image
        try:
            raster = self.viewModel.proj.getImage(roi.imageIndex).raster
            
            # Get ROI points
            points = roi.getLinePts()
            if points is None or len(points[0]) < 3:
                logger.warning("Not enough points to extract slice")
                return None
                
            # Convert points format to x,y pairs for polygon function
            polygon_points = np.array([points[0], points[1]]).T
            
            # Create a mask for the ROI
            from skimage.draw import polygon
            try:
                # Use polygon function with correct parameters
                rows, cols = raster.shape[:2]
                mask = np.zeros((rows, cols), dtype=bool)
                # Convert to integer values for polygon function
                r_coords = np.clip(np.array(points[1], dtype=int), 0, rows-1)
                c_coords = np.clip(np.array(points[0], dtype=int), 0, cols-1)
                
                rr, cc = polygon(r_coords, c_coords, mask.shape)
                mask[rr, cc] = True
                
                # Extract all bands from the masked area
                if mask.sum() > 0:
                    # Take all bands for each masked pixel
                    extracted_slice = raster[mask]
                    return extracted_slice
                else:
                    logger.warning("ROI mask contains no pixels")
                    return None
            except Exception as e:
                logger.error(f"Error creating ROI mask: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Error getting raster data: {str(e)}")
            return None
        
    def _onROIDrawn(self):
        """
        Handle the completion of an ROI drawing.
        Extracts the raster slice, creates a FreeHandROI, and adds it to the ProjectContext.
        """
        last_roi = self.freehandROIs[-1]
        
        # Get ROI data
        roi_points = last_roi.getLinePts()
        if roi_points is None or len(roi_points[0]) < 3:
            logger.warning("Invalid ROI: Not enough points")
            return
            
        roi_color = last_roi.color
        image_index = self.viewModel.index
        
        try:
            # Extract the array slice for the ROI
            array_slice = self.extractArraySlice(last_roi)
            
            # Create a FreeHandROI
            from core.entities.freehandROI import FreehandROI
            
            roi = FreehandROI(
                points=np.array(roi_points),
                image_indices=[image_index],  # Important: Pass as a list
                color=roi_color,
                array_slice=array_slice,
                mean_spectrum=np.nanmean(array_slice, axis=0) if array_slice is not None else None
            )
            
            # Add the ROI to the ProjectContext
            self.viewModel.proj.add_roi(roi, [image_index])  # Use new API
            
            logger.info(f"Saved ROI spectrum plot for image {image_index}.")
        except Exception as e:
            logger.error(f"Error creating ROI: {str(e)}", exc_info=True)


    @staticmethod
    def _initImageItem():
        """Initialize a new image item."""
        return pg.ImageItem(axisOrder="row-major", autoLevels=False, levels=(0, 1))

    @staticmethod
    def _initViewBox(name, imageItem):
        """Initialize a new view box."""
        viewBox = pg.ViewBox(
            name=name, lockAspect=True, enableMouse=False, invertY=True
        )
        viewBox.addItem(imageItem)
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
