# standard library

# third party imports
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# local imports
from gui.customitems.tripleimagehistogram import TripleImageHistogram


class ImageViewer(pg.GraphicsLayoutWidget):
    """
        A custom widget that displays an image with three views and a histogram.
        Provides main view, context, and zoom views of the image.

        Attributes:
            mainImageItem (pg.ImageItem): The main image item.
            mainView (pg.ViewBox): The main view box containing the main image.
            contextImageItem (pg.ImageItem): The context image item.
            contextView (pg.ViewBox): The view box containing the context image.
            zoomImageItem (pg.ImageItem): The zoomed-in image item.
            zoomView (pg.ViewBox): The view box containing the zoomed-in image.
            tripleHistogram (TripleImageHistogram): The histogram for the image.
        """

    def __init__(self):
        """
        Initializes the three views, the histogram, and ROI controls
        """
        super().__init__()
        self.mainImageItem = pg.ImageItem(axisOrder='row-major')
        self.mainView = self._initView(self.mainImageItem, 0, 0, 2,
                                       True)

        self.contextImageItem = pg.ImageItem(axisOrder='row-major')
        self.contextView = self._initView(self.contextImageItem, 0, 1, 1,
                                          False)

        self.zoomImageItem = pg.ImageItem(axisOrder='row-major')
        self.zoomView = self._initView(self.zoomImageItem, 1, 1, 1,
                                       False)

        self.tripleHistogram = TripleImageHistogram(self.mainImageItem,
                                                    self.contextImageItem,
                                                    self.zoomImageItem,
                                                    levelMode='rgba',
                                                    gradientPosition='bottom',
                                                    orientation='horizontal'
                                                    )

        self.addItem(self.tripleHistogram, 2, 0, 1, 2)

        self.contextROI = None

    def _initView(self, imageItem, row, col, rowspan, enableMouse):
        """
        Helper function to initialize an image item view
        @param imageItem:
        @param row:
        @param col:
        @param rowspan:
        @param enableMouse:
        @return:
        """
        viewBox = self.addViewBox(row=row, col=col,
                                  rowspan=rowspan,
                                  enableMouse=enableMouse)
        viewBox.setAspectLocked(True)
        viewBox.invertY()
        viewBox.addItem(imageItem)
        return viewBox

    def setImage(self, image):
        self.mainImageItem.setImage(image)
        self.contextImageItem.setImage(image)
        self.zoomImageItem.setImage(image)

        self._initROIS()

    def setMainImage(self, image):
        self.mainImageItem.setImage(image)
        self.resetLevels()

    def setContextAndZoomImage(self, image):
        self.contextImageItem.setImage(image)
        self.zoomImageItem.setImage(image)
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
        if self.contextROI is not None:
            self.clearROIs()
        imgRect = self.contextImageItem.boundingRect()
        center = (self.contextImageItem.mapToParent(imgRect.center()))

        startSize = (imgRect.width() / 4, imgRect.height() / 4)

        self.contextROI = pg.RectROI(center,
                                     startSize,
                                     pen=(0, 9),
                                     maxBounds=imgRect)

        self.contextView.addItem(self.contextROI)

        self.contextROI.sigRegionChanged.connect(self._updateZoomView)

        self._updateZoomView()

    def clearROIs(self):
        """
        Clears the existing ROIs
        """
        self.contextView.removeItem(self.contextROI)

    def _keepSquareROI(self):
        """
        Ensures the ROI shape is always square
        """
        size = self.contextROI.size()
        min_dim = min(size.x(), size.y())

        # Adjust the size to be square
        self.contextROI.setSize([min_dim, min_dim], update=False)

        # Reposition the scale handle
        handle = self.contextROI.handles[0]['item']
        handle.setPos(min_dim, min_dim)

    def _updateZoomView(self):
        """
        Updates the zoomed-in view based on the context ROI
        """
        # Alternative method where we actually extract the ROI from the image
        # subImage = self.contextROI.getArrayRegion(self.contextImageItem.image,
        #                                           self.contextImageItem)
        # self.zoomImageItem.setImage(subImage)

        self._keepSquareROI()

        roiPos = self.contextROI.pos()
        roiSize = self.contextROI.size()

        x_range = (roiPos.x(), roiPos.x() + roiSize.x())
        y_range = (roiPos.y(), roiPos.y() + roiSize.y())
        self.zoomView.setRange(xRange=x_range, yRange=y_range)
