# standard library
import logging

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
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
