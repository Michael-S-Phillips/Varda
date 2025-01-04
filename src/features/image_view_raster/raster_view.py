# standard library
import logging
from typing import override

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
from core.utilities import debug
from .raster_viewmodel import RasterViewModel

logger = logging.getLogger(__name__)


class RasterView(QWidget):
    """A custom widget that displays a view of an image in varda.
    has various signals and slots for linking this view with other views

    Attributes:
        mainImage (pg.ImageItem): The main image item.
        mainView (pg.ViewBox): The main view box containing the main image.
        contextImage (pg.ImageItem): The context image item.
        contextView (pg.ViewBox): The view box containing the context image.
        zoomImage (pg.ImageItem): The zoomed-in image item.
        zoomView (pg.ViewBox): The view box containing the zoomed-in image.
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

        # self.tripleHistogram: TripleImageHistogram

        self.contextROI: pg.RectROI = None
        self.mainROI: pg.RectROI = None

        self.stretchSelector: StretchSelector
        self.bandSelector: BandSelector

        self._initUI()
        self._initROIS()
        self._connectSignals()

    def _initUI(self):

        self.mainImage = pg.ImageItem(
            axisOrder="row-major", autoLevels=False, levels=(0, 1)
        )
        self.mainView = self._initViewBox("Main View", self.mainImage, False)

        self.contextImage = pg.ImageItem(
            axisOrder="row-major", autoLevels=False, levels=(0, 1)
        )
        self.contextView = self._initViewBox("Context View", self.contextImage, False)

        self.zoomImage = pg.ImageItem(
            axisOrder="row-major", autoLevels=False, levels=(0, 1)
        )
        self.zoomView = self._initViewBox("Zoom View", self.zoomImage, False)

        # self.tripleHistogram = TripleImageHistogram(self.mainImageItem,
        #                                             self.contextImageItem,
        #                                             self.zoomImageItem,
        #                                             levelMode='rgba',
        #                                             gradientPosition='bottom',
        #                                             orientation='horizontal'
        #                                             )

        mainGraphicsView = pg.GraphicsView()
        mainGraphicsView.setCentralItem(self.mainView)

        contextGraphicsView = pg.GraphicsView()
        contextGraphicsView.setCentralItem(self.contextView)

        zoomGraphicsView = pg.GraphicsView()
        zoomGraphicsView.setCentralItem(self.zoomView)

        histogramView = pg.GraphicsView()
        # histogramView.setCentralItem(self.tripleHistogram)

        verticalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        verticalSplitter.addWidget(contextGraphicsView)
        verticalSplitter.addWidget(zoomGraphicsView)

        horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        horizontalSplitter.addWidget(mainGraphicsView)
        horizontalSplitter.addWidget(verticalSplitter)

        mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        mainSplitter.addWidget(horizontalSplitter)
        mainSplitter.addWidget(histogramView)
        mainSplitter.setStretchFactor(0, 10)
        mainSplitter.setStretchFactor(1, 1)

        self.stretchSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.index, self
        )
        self.bandSelector = BandSelector(
            self.viewModel.proj, self.viewModel.index, self
        )
        selectorLayout = QtWidgets.QHBoxLayout()
        selectorLayout.addWidget(self.stretchSelector)
        selectorLayout.addWidget(self.bandSelector)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.addWidget(mainSplitter)
        self.setLayout(layout)

    def _connectSignals(self):
        # self.tripleHistogram.sigLevelsChanged.connect(self.updateModel)
        self.viewModel.sigStretchChanged.connect(self.onStretchChanged)
        self.viewModel.sigBandChanged.connect(self.onBandChanged)
        self.stretchSelector.currentIndexChanged.connect(self.viewModel.selectStretch)
        self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)

        self.contextROI.sigRegionChanged.connect(self._updateMainView)
        self.mainROI.sigRegionChanged.connect(self._updateZoomView)

    @staticmethod
    def _initViewBox(name, imageItem, enableMouse):
        """Helper function to initialize an image item view"""
        viewBox = pg.ViewBox(
            name=name, lockAspect=True, enableMouse=enableMouse, invertY=True
        )
        viewBox.addItem(imageItem)
        return viewBox

    def updateView(self):
        levels = self.viewModel.getSelectedStretch().toList()
        self.contextImage.setImage(self.viewModel.getRasterFromBand(), levels=levels)
        self._updateMainView()

    def _initROIS(self):
        """Initializes the ROI setup"""
        levels = self.viewModel.getSelectedStretch()
        self.contextImage.setImage(self.viewModel.getRasterFromBand(), levels=levels)

        if self.contextROI is not None or self.mainROI is not None:
            self.clearROIs()

        self.contextROI = self.getDefaultROI(self.contextImage)
        self.contextView.addItem(self.contextROI)
        self._updateMainView()

        self.mainROI = self.getDefaultROI(self.mainImage)
        self.mainView.addItem(self.mainROI)
        self._updateZoomView()

    @staticmethod
    def getDefaultROI(imageItem):
        imgRect = imageItem.boundingRect()
        center = imageItem.mapToParent(imgRect.center())
        startSize = (imgRect.width() / 4, imgRect.height() / 4)
        return pg.RectROI(center, startSize, pen=(0, 9), maxBounds=imgRect)

    def clearROIs(self):
        """Clears the existing ROIs"""
        self.contextView.removeItem(self.contextROI)
        self.mainView.removeItem(self.mainROI)

    @staticmethod
    def _keepSquareROI(roi):
        """Ensures the ROI shape is always square"""
        size = roi.size()
        minDim = min(size.x(), size.y())

        # Adjust the size to be square
        roi.setSize([minDim, minDim], update=False)

        # Reposition the scale handle
        handle = roi.handles[0]["item"]
        handle.setPos(minDim, minDim)

    def _updateMainView(self):
        """Updates the main view based on the context ROI"""
        if self.contextROI is None:
            return

        self._keepSquareROI(self.contextROI)
        levels = self.viewModel.getSelectedStretch().toList()
        self.mainImage.setImage(
            self.contextROI.getArrayRegion(self.contextImage.image, self.contextImage),
            levels=levels,
        )
        if self.mainROI is not None:
            self.mainROI.maxBounds = self.mainImage.boundingRect()
        self._updateZoomView()

    def _updateZoomView(self):
        """Updates the zoom view based on the main ROI"""
        if self.mainROI is None:
            return

        self._keepSquareROI(self.mainROI)

        levels = self.viewModel.getSelectedStretch().toList()
        self.zoomImage.setImage(
            self.mainROI.getArrayRegion(self.mainImage.image, self.mainImage),
            levels=levels,
        )

    # def updateModel(self):
    #     """Updates the model stretch based on the histogram region"""
    #     levels = self.tripleHistogram.getLevels()
    #     levels = [level for row in levels for level in row]
    #     self.setStretchValues(*levels)

    def onStretchChanged(self):
        """Updates the image levels based on the model stretch"""
        levels = self.viewModel.getSelectedStretch().toList()
        # self.tripleHistogram.setLevels(rgba=levels)

        self.mainImage.setLevels(levels)
        self.contextImage.setLevels(levels)
        self.zoomImage.setLevels(levels)

    def onBandChanged(self):
        """Updates the model band based on the band editor"""
        self.updateView()


# class TripleImageHistogram(pg.HistogramLUTItem):
#     """Allows us to control the levels of three images via a single histogram"""
#
#     def __init__(self, mainImage, contextImage, zoomImage, **kwargs):
#         super().__init__(contextImage, **kwargs)
#         self.mainImageHistogram = pg.HistogramLUTItem(mainImage, **kwargs)
#         self.zoomHistogram = pg.HistogramLUTItem(zoomImage, **kwargs)
#
#     @override
#     def regionChanging(self):
#         """override of the regionChanging method to update the levels of all three images"""
#         profile = debug.Profiler()
#         super().regionChanging()
#         self.mainImageHistogram.imageItem().setLevels(self.getLevels())
#         self.zoomHistogram.imageItem().setLevels(self.getLevels())
#         profile("Time to Update Histogram Levels")
