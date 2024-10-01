"""
spectralimagedisplay.py
"""
from typing import override
from PyQt6.QtWidgets import *
import numpy as np
import speclabimageprocessing
from pathlib import Path
import pyqtgraph as pg
from pyqtgraph import ImageView
import speclabimageprocessing as specLab


class SpectralImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralImageDisplay, self).__init__()
        self.setAcceptDrops(True)
        self.parent = parent
        self.vertices = []

    @override
    def dragEnterEvent(self, event):
        # if event.mimeData().hasFormat('image/hdr'):
        event.acceptProposedAction()

    @override
    def dropEvent(self, event):
        self.createPlt(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def createPlt(self, fileName):
        self.buttonLayout = QHBoxLayout()
        self.currentROI = None

        self.polylineROIButton = QPushButton("Poly ROI", self)
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

        print('Creating plt...')

        sdv = specLab.SpectralImage.new_image(fileName)
        # imv = pg.ImageView(self)
        self.show()
        self.setImage(np.array(sdv.image))

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


class SpectralZoomImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralContextImage, self).__init__(parent)
        self.ui.histogram.hide()
