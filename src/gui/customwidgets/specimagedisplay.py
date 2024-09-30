"""
specimagedisplay.py
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import numpy as np
import qimage2ndarray
import matplotlib.pyplot as plt
from gui.SpectralDataViewer import SpectralDataViewer
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from pathlib import Path
from gui.customwidgets.SpecNavigationToolbar import SpecNavigationToolbar
import pyqtgraph as pg
from pyqtgraph import ImageView

class SpectralImageDisplay(ImageView):
    
    def __init__(self, parent=None):
        super(SpectralImageDisplay, self).__init__()

        self.parent = parent
        self.vertices = []


    def createPlt(self, fileName):
        self.button_layout = QHBoxLayout()
        self.current_roi = None

        self.polyline_roi_button = QPushButton("Poly ROI", self)
        self.polyline_roi_button.clicked.connect(self.add_polyline_roi)
        self.polyline_roi_button.setStyleSheet("""
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
        self.button_layout.addWidget(self.polyline_roi_button)
    

        print('Creating plt...')

        sdv = SpectralDataViewer(fileName)
        # imv = pg.ImageView(self)
        self.show()
        self.setImage(np.array(sdv.image))

    def add_polyline_roi(self):
        if self.current_roi is not None:
            self.removeItem(self.current_roi)

        initial_points = [[100, 100], [100, 300], [300, 300], [300, 100]]
        self.current_roi = pg.PolyLineROI(initial_points, closed=True, pen=(10, 15, 10))
        self.current_roi.sigRegionChanged.connect(self.update_roi)
        self.addItem(self.current_roi)

    def update_roi(self):
        if isinstance(self.current_roi, pg.PolyLineROI):
            print(f"Polyline ROI points: {self.current_roi.getState()['points']}")



class SpectralZoomImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(SpectralImageDisplay):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()
