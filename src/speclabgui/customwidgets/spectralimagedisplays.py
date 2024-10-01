"""
spectralimagedisplay.py
"""
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph import ImageView


class SpectralMainImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralMainImageDisplay, self).__init__(parent)
        self.setAcceptDrops(True)

        self.buttonLayout = None
        self.currentROI = None
        self.vertices = []

        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.currentROI = None

        self.polylineROIButton = QtWidgets.QPushButton("Poly ROI", self)
        self.polylineROIButton.clicked.connect(self.addPolylineROI)
        self.polylineROIButton.setStyleSheet("""
            QPushButton {
                background-color: white;
                width: 80px;
                height: 20px;
                color: black;
                font-size: 10px;
                border-radius: 5px;
                border: 1px solid black;

            }
            QPushButton:hover {
                background-color: lightgray;
            }
        """)
        self.buttonLayout.addWidget(self.polylineROIButton)

    def addRectangularROI(self):
        if self.currentROI is not None:
            self.removeItem(self.currentROI)

        self.currentROI = pg.RectROI([100, 100], [100, 100], pen=(10, 9, 100))
        self.currentROI.sigRegionChanged.connect(self.updateROI)
        self.addItem(self.currentROI)

    def addPolylineROI(self):
        if self.currentROI is not None:
            self.removeItem(self.currentROI)

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
