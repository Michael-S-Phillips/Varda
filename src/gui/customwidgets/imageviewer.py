# standard library

# third party imports
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

# local imports
from gui.customitems.tripleimagehistogram import TripleImageHistogram


class ImageViewer(pg.GraphicsLayoutWidget):
    def __init__(self):
        super().__init__()
        self.mainImageItem = pg.ImageItem(axisOrder='row-major')
        self.mainView = self.initImageItemView(self.mainImageItem, 0, 0, 2, True)

        self.contextImageItem = pg.ImageItem(axisOrder='row-major')
        self.contextView = self.initImageItemView(self.contextImageItem, 0, 1, 1, False)

        self.zoomImageItem = pg.ImageItem(axisOrder='row-major')
        self.zoomView = self.initImageItemView(self.zoomImageItem, 1, 1, 1, False)

        self.tripleHistogramRed = TripleImageHistogram(self.mainImageItem,
                                                       self.contextImageItem,
                                                       self.zoomImageItem,
                                                       levelMode='rgba',
                                                       gradientPosition='bottom',
                                                       orientation='horizontal'
                                                       )

        self.addItem(self.tripleHistogramRed, 2, 0, 1, 2)

    def initImageItemView(self, imageItem, row, col, rowspan, enableMouse):
        viewBox = self.addViewBox(row=row, col=col,
                                                 rowspan=rowspan,
                                                 enableMouse=enableMouse)
        viewBox.setAspectLocked(True)
        viewBox.invertY()
        viewBox.addItem(imageItem)
        return viewBox

    def setImage(self, imageItem):
        self.mainImageItem.setImage(imageItem)
        self.contextImageItem.setImage(imageItem)
        self.zoomImageItem.setImage(imageItem)
