"""
specimagedisplay.py
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from . import BasicWidget
import numpy as np
import qimage2ndarray
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from gui.SpectralDataViewer import SpectralDataViewer
import matplotlib
matplotlib.use('QtAgg')

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

class SpectralImageDisplay(FigureCanvasQTAgg):
    def __init__(self, parent):
        super(SpectralImageDisplay, self).__init__()

        self.label = QLabel(self)
        #self.array = np.ones((512, 512, 3), dtype=np.uint8)
        #self.image = qimage2ndarray.array2qimage(self.array, normalize=(0, 1))
        #self.label.setPixmap(QPixmap(self.image))

        # self.setImage(np.ones((self.width(), self.height(), 3), dtype=np.uint8))
        self.figure, self.ax = plt.subplots(figsize=(6, 6))
        self.canvas = FigureCanvas(self.figure)

        #self.contextImage = TextWidget("Context Image")
        #self.zoomImage = TextWidget("Zoom Image")

    def setImage(self, img: np.ndarray):
        self.label.clear()
        self.label.setPixmap(QPixmap(qimage2ndarray.array2qimage(img, normalize=(0, 1))))
        self.label.show()
    
    def createPlt(self, fileName):
        print('Creating plt...')
        sdv = SpectralDataViewer(fileName)
        self.ax.imshow(np.array(sdv.image))
        self.canvas.draw()



