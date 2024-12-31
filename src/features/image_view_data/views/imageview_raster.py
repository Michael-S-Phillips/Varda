# standard library
import logging
from typing import override

# third party imports
from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg

# local imports
from features.image_view_data.viewmodels.image_viewmodel import ImageViewModel
from .base_imageview import BaseImageView
from core.utilities import debug

logger = logging.getLogger(__name__)


class ImageViewRaster(BaseImageView):
    """
        A custom widget that displays a view of an image in varda.
        has various signals and slots for linking this view with other views

        Attributes:
            mainImageItem (pg.ImageItem): The main image item.
            mainView (pg.ViewBox): The main view box containing the main image.
            contextImageItem (pg.ImageItem): The context image item.
            contextView (pg.ViewBox): The view box containing the context image.
            zoomImageItem (pg.ImageItem): The zoomed-in image item.
            zoomView (pg.ViewBox): The view box containing the zoomed-in image.
            tripleHistogram (TripleImageHistogram): The histogram for the image.
    """

    def __init__(self, viewmodel: ImageViewModel, parent=None):
        """
        Initializes the three views, the histogram, and ROI controls
        """
        super().__init__(viewmodel, parent)

        self.mainView: pg.ViewBox
        self.contextView: pg.ViewBox
        self.zoomView: pg.RectROI

        self.mainImageItem: pg.ImageItem
        self.contextImageItem: pg.ImageItem
        self.zoomImageItem: pg.ImageItem

        self.tripleHistogram: TripleImageHistogram

        self.contextROI: pg.RectROI
        self.mainROI: pg.RectROI

        self._initUI()

        self.imageModel = viewmodel

        if viewmodel:
            self.setViewmodel(viewmodel)

        self.tripleHistogram.sigLevelsChanged.connect(self.updateModel)

    def _initViewBox(self, name, imageItem, enableMouse):
        """
        Helper function to initialize an image item view
        @param name: The name of the view
        @param imageItem: The image item to add to the view
        @param row:
        @param col:
        @param rowspan:
        @param enableMouse:
        @return:
        """
        viewBox = pg.ViewBox(name=name, lockAspect=True,
                             enableMouse=enableMouse, invertY=True)
        viewBox.addItem(imageItem)
        return viewBox

    def _initUI(self):

        self.mainImageItem = pg.ImageItem(axisOrder='row-major',
                                          autoLevels=False,
                                          levels=(0, 1))
        self.mainView = self._initViewBox("Main View",
                                          self.mainImageItem,
                                          False)

        self.contextImageItem = pg.ImageItem(axisOrder='row-major',
                                             autoLevels=False,
                                             levels=(0, 1))
        self.contextView = self._initViewBox("Context View",
                                             self.contextImageItem,
                                             False)

        self.zoomImageItem = pg.ImageItem(axisOrder='row-major',
                                          autoLevels=False,
                                          levels=(0, 1))
        self.zoomView = self._initViewBox("Zoom View",
                                          self.zoomImageItem,
                                          False)

        self.tripleHistogram = TripleImageHistogram(self.mainImageItem,
                                                    self.contextImageItem,
                                                    self.zoomImageItem,
                                                    levelMode='rgba',
                                                    gradientPosition='bottom',
                                                    orientation='horizontal'
                                                    )

        self.mainGraphicsView = pg.GraphicsView()
        self.mainGraphicsView.setCentralItem(self.mainView)

        self.contextGraphicsView = pg.GraphicsView()
        self.contextGraphicsView.setCentralItem(self.contextView)

        self.zoomGraphicsView = pg.GraphicsView()
        self.zoomGraphicsView.setCentralItem(self.zoomView)

        self.histogramView = pg.GraphicsView()
        self.histogramView.setCentralItem(self.tripleHistogram)

        self.verticalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.verticalSplitter.addWidget(self.contextGraphicsView)
        self.verticalSplitter.addWidget(self.zoomGraphicsView)

        self.horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.horizontalSplitter.addWidget(self.mainGraphicsView)
        self.horizontalSplitter.addWidget(self.verticalSplitter)

        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.mainSplitter.addWidget(self.horizontalSplitter)
        self.mainSplitter.addWidget(self.histogramView)
        self.mainSplitter.setStretchFactor(0, 10)
        self.mainSplitter.setStretchFactor(1, 1)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.mainSplitter)
        self.setViewLayout(layout)

    def setViewmodel(self, image):
        super().setViewmodel(image)

        self.contextImageItem.setImage(self.getRasterDataSlice())
        self._initROIS()

    def updateView(self):
        self.contextImageItem.setImage(self.getRasterDataSlice())
        self._updateMainView()
        self.onStretchChanged()

    def _initROIS(self):
        """
        Initializes the ROIs for the context view
        Returns:
        """
        if self.contextROI is not None or self.mainROI is not None:
            self.clearROIs()
        imgRect = self.contextImageItem.boundingRect()
        center = (self.contextImageItem.mapToParent(imgRect.center()))

        startSize = (imgRect.width() / 4, imgRect.height() / 4)

        self.contextROI = pg.RectROI(center,
                                     startSize,
                                     pen=(0, 9),
                                     maxBounds=imgRect)

        self.contextView.addItem(self.contextROI)
        self.contextROI.sigRegionChanged.connect(self._updateMainView)
        self._updateMainView()

        imgRect = self.mainImageItem.boundingRect()
        center = (self.mainImageItem.mapToParent(imgRect.center()))
        startSize = (imgRect.width() / 4, imgRect.height() / 4)

        self.mainROI = pg.RectROI(center,
                                  startSize,
                                  pen=(0, 9),
                                  maxBounds=imgRect)

        self.mainView.addItem(self.mainROI)
        self.mainROI.sigRegionChanged.connect(self._updateZoomView)
        self._updateZoomView()

    def clearROIs(self):
        """
        Clears the existing ROIs
        """
        self.contextView.removeItem(self.contextROI)
        self.mainView.removeItem(self.mainROI)

    def _keepSquareROI(self, roi):
        """
        Ensures the ROI shape is always square
        """
        size = roi.size()
        minDim = min(size.x(), size.y())

        # Adjust the size to be square
        roi.setSize([minDim, minDim], update=False)

        # Reposition the scale handle
        handle = roi.handles[0]['item']
        handle.setPos(minDim, minDim)

    def _updateMainView(self):
        """
        Updates the main view based on the context ROI
        """
        if self.contextROI is None:
            return

        self._keepSquareROI(self.contextROI)
        self.mainImageItem.setImage(
            self.contextROI.getArrayRegion(self.contextImageItem.image,
                                           self.contextImageItem),
            levels=(0, 1), autoLevels=False
        )
        if self.mainROI is not None:
            self.mainROI.maxBounds = self.mainImageItem.boundingRect()

        self._updateZoomView()

    def _updateZoomView(self):
        """
        Updates the zoom view based on the main ROI
        """
        if self.mainROI is None:
            return
        self._keepSquareROI(self.mainROI)
        self.zoomImageItem.setImage(
            self.mainROI.getArrayRegion(self.mainImageItem.image,
                                        self.mainImageItem),
            levels=(0, 1), autoLevels=False
        )
        self.onStretchChanged()  # kinda hacky workaround to prevent the image
        # from losing its stretch settings

    def updateModel(self):
        """
        Updates the model stretch based on the histogram region
        """
        levels = self.tripleHistogram.getLevels()
        levels = [level for row in levels for level in row]
        self.setStretchValues(*levels)

    def onStretchChanged(self):
        """
        Updates the image levels based on the model stretch
        """
        levels = self.getStretch().values
        self.tripleHistogram.setLevels(rgba=levels)

        self.mainImageItem.setLevels(levels)
        self.contextImageItem.setLevels(levels)
        self.zoomImageItem.setLevels(levels)

    def onBandChanged(self):
        """
        Updates the model band based on the band editor
        """
        self.updateView()


class TripleImageHistogram(pg.HistogramLUTItem):
    """
    Allows us to control the levels of three images via a single histogram
    """
    def __init__(self, mainImage, contextImage, zoomImage, **kwargs):
        super().__init__(contextImage, **kwargs)
        self.mainImageHistogram = pg.HistogramLUTItem(mainImage, **kwargs)
        self.zoomHistogram = pg.HistogramLUTItem(zoomImage, **kwargs)

    @override
    def regionChanging(self):
        """
        override of the regionChanging method to update the levels of all three images
        """
        profile = debug.Profiler()
        super().regionChanging()
        self.mainImageHistogram.imageItem().setLevels(self.getLevels())
        self.zoomHistogram.imageItem().setLevels(self.getLevels())
        profile("Time to Update Histogram Levels")
