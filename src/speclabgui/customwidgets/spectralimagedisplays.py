"""
spectralimagedisplay.py
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QMenu
import pyqtgraph as pg
from pyqtgraph import ImageView


class SpectralMainImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralMainImageDisplay, self).__init__(parent)
        self.setAcceptDrops(True)

        self.buttonLayout = None
        self.currentROI = None
        self.vertices = []
        self.savedROIS = []

        self.buttonLayout = QtWidgets.QHBoxLayout()
        
        self.currentROI = None

        self.options = QtWidgets.QPushButton("Options", self)
        self.options.clicked.connect(self.showMenu)

        self.menuButton = QMenu(self)
        self.menuButton.addAction("Poly ROI", self.addPolylineROI)
        self.menuButton.addAction("Save ROI", self.saveROI)
        self.menuButton.addAction("Load ROI", self.loadROI)


        # self.polylineROIButton = QtWidgets.QPushButton("Poly ROI", self)
        # self.polylineROIButton.clicked.connect(self.addPolylineROI)
        # self.polylineROIButton.setStyleSheet("""
        #     QPushButton {
        #         background-color: white;
        #         width: 80px;
        #         height: 20px;
        #         color: black;
        #         font-size: 10px;
        #         border-radius: 5px;
        #         border: 1px solid black;

        #     }
        #     QPushButton:hover {
        #         background-color: lightgray;
        #     }
        # """)
        # self.buttonLayout.addWidget(self.polylineROIButton)

        # add button to save ROI state
        # self.menu = QMenu(self)

        # self.saveROIButton = QtWidgets.QPushButton("Save ROI", self)
        # self.saveROIButton.clicked.connect(self.saveROI)

        # self.loadROIButton = QtWidgets.QPushButton("Load ROI", self)
        # self.loadROIButton.clicked.connect(self.loadROI)

    def loadROI(self):
        if (self.savedROIS != []):
            for i in range(len(self.savedROIS)):
                self.menuButton.addAction("ROI "+ str(i+1), self.loadROIState(i))
            self.showMenu()
        else:
            self.loadROIButton.setEnabled(False)

    def showMenu(self):
        self.menuButton.exec(self.options.mapToGlobal(self.options.rect().bottomLeft()))

        
    def loadROIState(self, i):
        self.currentROI.setState(self.savedROIS[i])


    def saveROI(self):
        if (self.currentROI != None):
            state = self.currentROI.saveState()
            self.savedROIS.append(state)

    def addRectangularROI(self):
        if self.currentROI is not None:
            self.removeItem(self.currentROI)

        self.currentROI = pg.RectROI([100, 100], [100, 100], pen=(10, 9, 100))
        self.currentROI.sigRegionChanged.connect(self.updateROI)
        self.addItem(self.currentROI)

    def addPolylineROI(self):
        if self.currentROI is not None:
            self.savedROIS.append(self.currentROI)

        initial_points = [[100, 100], [100, 300], [300, 300], [300, 100]]
        self.currentROI = pg.PolyLineROI(initial_points, closed=True, pen=(10, 15, 10))
        self.currentROI.sigRegionChanged.connect(self.updateROI)
        self.addItem(self.currentROI)

    def updateROI(self):
        if isinstance(self.currentROI, pg.PolyLineROI):
            print(f"Polyline ROI points: {self.currentROI.getState()['points']}")


class SpectralZoomImage(ImageView):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(ImageView):
    def __init__(self, parent):
        super(SpectralContextImage, self).__init__(parent)
        self.ui.histogram.hide()
