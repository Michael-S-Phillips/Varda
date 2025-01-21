# standard library
import logging

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg
import numpy as np
from scipy.spatial import ConvexHull
from skimage.draw import polygon

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
from gui.widgets.ROI_selector import ROISelector
from core.entities.freehandROI import FreeHandROI
from .raster_viewmodel import RasterViewModel

logger = logging.getLogger(__name__)

# TODO: This feature is a little messy and could probably be structured more cleanly.
#  Maybe by moving more of the functionality and state-tracking the viewModel.


class RasterView(QWidget):
    """A custom widget that displays a view of an image in varda.
    has various signals and slots for linking this view with other views

    Attributes:
        contextImage (pg.ImageItem): Shows the entire image.
        contextROI (pg.rectROI): adjustable ROI overtop contextImage.
        contextView (pg.ViewBox): Container for contextImage and its ROI.
        mainImage (pg.ImageItem): Shows the image region selected by contextROI.
        mainROI (pg.RectROI): adjustable ROI overtop mainImage.
        mainView (pg.ViewBox): Container for mainImage and its ROI.
        zoomImage (pg.ImageItem):  Shows the image region selected by mainROI.
        zoomView (pg.ViewBox): Container for zoomImage.
    """

    def __init__(self, viewmodel: RasterViewModel, parent=None):
        """Initializes the three views, the histogram, and ROI controls"""
        super().__init__(parent=parent)
        self.viewModel = viewmodel

        self.mainView: pg.ViewBox
        self.contextView: pg.ViewBox
        self.zoomView: pg.RectROI

        self.mainImage: pg.ImageItem
        self.contextImage: pg.ImageItem
        self.zoomImage: pg.ImageItem

        self.contextROI: pg.RectROI = None
        self.mainROI: pg.RectROI = None

        self.stretchSelector: StretchSelector
        self.bandSelector: BandSelector

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

        self._initUI()
        self._initROIS()
        self._connectSignals()


    def _initUI(self):
        self.mainImage = self._initImageItem()
        self.contextImage = self._initImageItem()
        self.zoomImage = self._initImageItem()

        self.mainView = self._initViewBox("Main View", self.mainImage)
        self.contextView = self._initViewBox("Context View", self.contextImage)
        self.zoomView = self._initViewBox("Zoom View", self.zoomImage)

        self.stretchSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.index, self
        )
        self.bandSelector = BandSelector(
            self.viewModel.proj, self.viewModel.index, self
        )
        self._buildLayout()

    def _buildLayout(self):
        mainGraphicsView = pg.GraphicsView()
        mainGraphicsView.setCentralItem(self.mainView)

        contextGraphicsView = pg.GraphicsView()
        contextGraphicsView.setCentralItem(self.contextView)

        zoomGraphicsView = pg.GraphicsView()
        zoomGraphicsView.setCentralItem(self.zoomView)

        verticalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        verticalSplitter.addWidget(contextGraphicsView)
        verticalSplitter.addWidget(zoomGraphicsView)

        horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        horizontalSplitter.addWidget(mainGraphicsView)
        horizontalSplitter.addWidget(verticalSplitter)

        mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        mainSplitter.addWidget(horizontalSplitter)
        # make the mainView larger than the zoom/context views.
        mainSplitter.setStretchFactor(0, 10)
        mainSplitter.setStretchFactor(1, 1)

        selectorLayout = QtWidgets.QHBoxLayout()
        selectorLayout.addWidget(self.stretchSelector)
        selectorLayout.addWidget(self.bandSelector)

        first_roi = ROISelector(None)
        first_roi.setImageIndex(self.viewModel.index)
        self.freehandROIs.append(first_roi)
        mainGraphicsView.addItem(self.freehandROIs[0])

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.addWidget(mainSplitter)
        self.setLayout(layout)

    def _connectSignals(self):
        # signals so viewmodel can tell us when to update
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)
        self.viewModel.sigBandChanged.connect(self._onBandChanged)

        # signals so we can tell the viewmodel that the user selected a new band/stretch
        self.stretchSelector.currentIndexChanged.connect(self.viewModel.selectStretch)
        self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)

        # signals for ROI functionality
        self.contextROI.sigRegionChanged.connect(self._updateMainView)
        self.mainROI.sigRegionChanged.connect(self._updateZoomView)

        self.freehandROIs[-1].sigDrawingComplete.connect(self._onROIDrawn)
        


    def _initROIS(self):
        # creates new ROIs and inserts them into the views.
        self.clearROIs()

        # because we rely on the size of the imageItem to position the ROI, we need
        # to set the image BEFORE adding an ROI to it, hence the process of
        # update context -> add context ROI -> update main -> add ROI...
        # TODO: There is almost certainly a better way to set this up. But I'll come
        #  back to it later.
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self.contextROI = self._getDefaultROI(self.contextImage)
        self.contextView.addItem(self.contextROI)

        self._updateMainView()
        self.mainROI = self._getDefaultROI(self.mainImage)
        self.mainView.addItem(self.mainROI)

        self._updateZoomView()

    def clearROIs(self):
        """Clears the existing ROIs"""
        if self.contextROI is not None:
            self.contextView.removeItem(self.contextROI)
        if self.mainROI is not None:
            self.mainView.removeItem(self.mainROI)

    def _updateViews(self):
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self._updateMainView()

    def _updateMainView(self):
        """Updates the main view based on the context ROI"""
        if self.contextROI is None:
            return

        self._makeROISquare(self.contextROI)

        image = self.contextROI.getArrayRegion(
            self.contextImage.image, self.contextImage
        )
        self._updateImageItem(self.mainImage, image)

        if self.mainROI is not None:
            # force mainROI to update so that it gets readjusted to be inside new
            # image range.
            self.mainROI.maxBounds = self.mainImage.boundingRect()
            currentPos = self.mainROI.pos()
            self.mainROI.setPos(currentPos + QtCore.QPointF(1, 1))  # Small nudge
            self.mainROI.setPos(currentPos)  # Reset back to original position
        self._updateZoomView()

    def _updateZoomView(self):
        """Updates the zoom view based on the main ROI"""
        if self.mainROI is None:
            return

        self._makeROISquare(self.mainROI)

        image = self.mainROI.getArrayRegion(self.mainImage.image, self.mainImage)
        self._updateImageItem(self.zoomImage, image)

    def _updateImageItem(self, imageItem, rasterData):
        levels = self.viewModel.getSelectedStretch().toList()
        imageItem.setImage(rasterData, levels=levels)

    def _onStretchChanged(self):
        """Updates the image levels based on the model stretch"""
        levels = self.viewModel.getSelectedStretch().toList()
        # self.tripleHistogram.setLevels(rgba=levels)

        self.mainImage.setLevels(levels)
        self.contextImage.setLevels(levels)
        self.zoomImage.setLevels(levels)

    def _onBandChanged(self):
        """Updates the model band based on the band editor"""
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
            roi (FreeHandROI): The ROI object containing points.

        Returns:
            np.ndarray: The raster slice bounded by the ROI.
        """
        # Get raster data for the current image
        raster = self.viewModel.proj.getImage(roi.imageIndex).raster

        # Convert ROI points to integer indices
        points = np.array(roi.getLinePts(), dtype=int)

        # Compute a convex hull or polygon mask
        if len(points) > 2:
            hull = ConvexHull(points)
            polygon_points = points[hull.vertices]
        else:
            polygon_points = points

        # Create a mask for the ROI
        rr, cc = polygon(polygon_points[:, 1], polygon_points[:, 0], raster.shape[:2])
        mask = np.zeros(raster.shape[:2], dtype=bool)
        mask[rr, cc] = True

        # Apply the mask to extract the slice
        extracted_slice = raster[mask]
        print(extracted_slice)
        return extracted_slice
    
    def _onROIDrawn(self):
        """
        Handle the completion of an ROI drawing.
        Extracts the raster slice, creates a FreeHandROI, and adds it to the ProjectContext.
        """
        last_roi = self.freehandROIs[-1]

        # Get ROI data
        roi_points = last_roi.getLinePts()
        roi_color = last_roi.color
        image_index = self.viewModel.index

        # Extract the array slice for the ROI
        array_slice = self.extractArraySlice(last_roi)

        # Create a FreeHandROI and add it to the ProjectContext
        roi = FreeHandROI(
            points=roi_points,
            color=roi_color,
            imageIndex=image_index,
            arraySlice=array_slice,
        )
        self.viewModel.proj.addROI(image_index, roi)


    @staticmethod
    def _initImageItem():
        return pg.ImageItem(axisOrder="row-major", autoLevels=False, levels=(0, 1))

    @staticmethod
    def _initViewBox(name, imageItem):
        """Helper function to initialize an image item view"""
        viewBox = pg.ViewBox(
            name=name, lockAspect=True, enableMouse=False, invertY=True
        )
        viewBox.addItem(imageItem)
        return viewBox

    @staticmethod
    def _getDefaultROI(imageItem):
        imgRect = imageItem.boundingRect()
        center = imageItem.mapToParent(imgRect.center())
        startSize = (imgRect.width() / 4, imgRect.height() / 4)
        return pg.RectROI(center, startSize, pen=(0, 9), maxBounds=imgRect)

    @staticmethod
    def _makeROISquare(roi):
        """Ensures the ROI is square."""
        size = roi.size()
        minDim = min(size.x(), size.y())

        # Adjust the size to be square
        roi.setSize([minDim, minDim], update=False)

        # Reposition the scale handle
        handle = roi.handles[0]["item"]
        handle.setPos(minDim, minDim)

   