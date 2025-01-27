import logging
import numpy as np
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg

from features.shared.selection_controls import StretchSelector, BandSelector
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

    def __init__(self, viewmodel: RasterViewModel, parent=None):
        super().__init__(parent=parent)
        self.viewModel = viewmodel

        # Initialize separate window for pixel plot
        self.pixel_plot_window = PixelPlotWindow()

        # Initialize image items and views
        self.mainImage = self._initImageItem()
        self.contextImage = self._initImageItem()
        self.zoomImage = self._initImageItem()

        self.mainView = None
        self.contextView = None
        self.zoomView = None

        self.contextROI = None
        self.mainROI = None

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
            logger.debug(f"Metadata wavelength shape: {image.metadata.wavelength.shape}")
            logger.debug(f"First few wavelengths: {image.metadata.wavelength[:5]}")
            logger.debug(
                f"Wavelength range: {image.metadata.wavelength.min():.2f} - {image.metadata.wavelength.max():.2f} nm")
        except Exception as e:
            logger.error(f"Error logging image info: {str(e)}")

    def _initUI(self):
        """Initialize the user interface components."""
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

        # Create main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.addWidget(horizontalSplitter)
        self.setLayout(layout)

    def zoomImageClicked(self, event):
        """Handle clicks on the zoom image."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            try:
                # Get click position
                pos = event.pos()
                x, y = int(pos.x()), int(pos.y())

                # Get image and raster data
                image = self.viewModel.proj.getImage(self.viewModel.index)
                raster_data = image.raster

                # Calculate coordinates in original image space
                main_roi_pos = self.mainROI.pos()
                context_roi_pos = self.contextROI.pos()
                final_x = int(context_roi_pos.x() + main_roi_pos.x() + x)
                final_y = int(context_roi_pos.y() + main_roi_pos.y() + y)

                # Update display if coordinates are valid
                if (0 <= final_x < raster_data.shape[1] and
                        0 <= final_y < raster_data.shape[0]):
                    # Update crosshairs
                    self.crosshair_v.setPos(x)
                    self.crosshair_h.setPos(y)

                    # Get spectral data
                    spectral_data = raster_data[final_y, final_x, :]

                    # Get wavelengths from image metadata
                    wavelengths = image.metadata.wavelength
                    logger.debug(f"Wavelength data from metadata: {wavelengths[:5]}...")  # Log first 5 values
                    logger.debug(f"Wavelength array shape: {wavelengths.shape if wavelengths is not None else 'None'}")
                    logger.debug(f"Raster shape: {raster_data.shape}")

                    if wavelengths is None or len(wavelengths) == 0 or len(wavelengths) != raster_data.shape[2]:
                        logger.warning(f"Invalid wavelength data detected. Using band numbers instead.")
                        wavelengths = np.arange(raster_data.shape[2])
                    else:
                        logger.info(f"Using wavelength range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")

                    # Update plot window
                    self.pixel_plot_window.update_plot(wavelengths, spectral_data, (final_x, final_y))

            except Exception as e:
                logger.error(f"Error updating pixel plot: {str(e)}")

        event.accept()

    def _connectSignals(self):
        """Connect ROI signals."""
        if self.contextROI:
            self.contextROI.sigRegionChanged.connect(self._updateMainView)
        if self.mainROI:
            self.mainROI.sigRegionChanged.connect(self._updateZoomView)

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