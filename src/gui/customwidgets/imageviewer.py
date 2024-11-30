# standard library
from typing import Optional

# third party imports
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QModelIndex
import pyqtgraph as pg

# local imports
from gui.customitems import TripleImageHistogram
from src.models.imagemodel import ImageModel


class ImageViewer(QtWidgets.QWidget):
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

    def __init__(self, imageModel=Optional[ImageModel] | None):
        """
        Initializes the three views, the histogram, and ROI controls
        """
        super().__init__()

        self.mainImageItem = pg.ImageItem(axisOrder='row-major',
                                          autoLevels=False,
                                          levels=(0, 1))
        self.mainView = self._initView("Main View",
                                       self.mainImageItem,
                                       False)

        self.contextImageItem = pg.ImageItem(axisOrder='row-major',
                                             autoLevels=False,
                                             levels=(0, 1))
        self.contextView = self._initView("Context View",
                                          self.contextImageItem,
                                          False)

        self.zoomImageItem = pg.ImageItem(axisOrder='row-major',
                                          autoLevels=False,
                                          levels=(0, 1))
        self.zoomView = self._initView("Zoom View",
                                       self.zoomImageItem,
                                       False)

        self.imageItem = pg.ImageItem(axisOrder='row-major',
                                      autoLevels=False,
                                      levels=(0, 1))
        self.view = self._initView("Main View", self.imageItem, False)

        self.tripleHistogram = TripleImageHistogram(self.mainImageItem,
                                                    self.contextImageItem,
                                                    self.zoomImageItem,
                                                    levelMode='rgba',
                                                    gradientPosition='bottom',
                                                    orientation='horizontal'
                                                    )

        self.stretchSelector = QtWidgets.QComboBox()
        self.stretchTableView = QtWidgets.QTableView()
        self.stretchSelector.setView(self.stretchTableView)

        self.contextROI = None
        self.mainROI = None

        self._initUI()

        self.imageModel = None
        if imageModel:
            self.setImage(imageModel)

    def _initView(self, name, imageItem, enableMouse):
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
        self.verticalSplitter.addWidget(self.stretchSelector)

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
        self.setLayout(layout)

    def setImage(self, image):
        self.imageModel = image
        image.imageChanged.connect(self.updateView)
        self.contextImageItem.setImage(self.imageModel.imageSlice)
        self._initROIS()

        self.stretchTableView.setModel(self.imageModel.stretchTable)
        self.stretchSelector.currentIndexChanged.connect(self.updateStretch)

    def updateView(self, image):

        self.contextImageItem.setImage(image)
        self._updateMainView()
        self.resetLevels()

    def resetLevels(self):
        """
        Resets the levels of the images to their original values
        """
        self.tripleHistogram.regionChanging()

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
        min_dim = min(size.x(), size.y())

        # Adjust the size to be square
        roi.setSize([min_dim, min_dim], update=False)

        # Reposition the scale handle
        handle = roi.handles[0]['item']
        handle.setPos(min_dim, min_dim)

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

    def updateStretch(self, stretchIndex: QModelIndex):
        """
        Updates the stretch of the image
        @param stretch:
        @param stretchIndex:
        @return:
        """
        stretch = stretchIndex.internalPointer()
        self.mainImageItem.setLevels(stretch)
        self.contextImageItem.setLevels(stretch)
        self.zoomImageItem.setLevels(stretch)
