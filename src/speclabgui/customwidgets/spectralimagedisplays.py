"""
spectralimagedisplay.py
"""
from typing import override

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMenu
import pyqtgraph as pg
from pyqtgraph import ImageView, InfiniteLine
from pyqtgraph.functions import mkPen, Colors
from speclabgui.customwidgets.ROIWindow import ROIWindow

color_keys = ['b', 'g', 'r', 'c', 'm', 'y', 'w']

class SpectralMainImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralMainImageDisplay, self).__init__(parent)
        self.ui.histogram.setLevelMode("rgba")
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.setAcceptDrops(True)

        self.buttonLayout = None
        self.currentROIs = []
        self.currentROI = None
        self.vertices = []
        self.savedROIS = []

        self.buttonLayout = QtWidgets.QHBoxLayout()
        
        self.currentROI = None

        self.options = QtWidgets.QPushButton("Options", self)
        self.options.clicked.connect(self.showMenu)

        self.menuButton = QMenu(self)
        self.menuButton.addAction("Poly ROI", self.addPolylineROI)
        self.buttonLayout.addWidget(self.options)

        self.menuButton.addAction("Save ROI", self.saveROI)
        self.menuButton.addAction("Load ROI", self.loadROI)

    def loadROI(self):
        roiPopupWindow = ROIWindow(self, self.savedROIS)
        roiPopupWindow.show()

    def showMenu(self):
        self.menuButton.exec(self.options.mapToGlobal(self.options.rect().bottomLeft()))
        
    def loadROIState(self, i):
        self.currentROI.setState(self.savedROIS[i])

    def saveROI(self):
        if (self.currentROI != None):
            state = self.currentROI.saveState()
            self.savedROIS.append(state)

    def addPolylineROI(self):
        if self.currentROI is not None and self.currentROI not in self.savedROIS:
            self.savedROIS.append(self.currentROI)

        initial_points = [[100, 100], [100, 300], [300, 300], [300, 100]]
        
        self.currentROI = pg.PolyLineROI(initial_points, closed=True)
        self.currentROI.setPen(mkPen(cosmetic=False, width=2, color=Colors[color_keys[len(self.currentROIs)]]))
        self.currentROIs.append(self.currentROI)

        for ROI in self.currentROIs:
            self.addItem(ROI)


    """
    we override this method so we can add a image parameter. calling this method is faster than SetImage,
    but assumes that the new image will work with the same parameters as the previous image.
    """
    @override
    def updateImage(self, image=None, autoHistogramRange=False):
        if image is not None:
            self.image = image
            self.imageDisp = None
        super().updateImage(autoHistogramRange=autoHistogramRange)


class SpectralZoomImage(ImageView):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(ImageView):
    def __init__(self, parent):
        super(SpectralContextImage, self).__init__(parent)
        self.ui.histogram.hide()
