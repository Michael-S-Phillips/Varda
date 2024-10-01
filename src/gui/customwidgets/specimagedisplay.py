from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtGui import QPixmap
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import numpy as np
import qimage2ndarray
from gui.SpectralDataViewer import SpectralDataViewer


class SpectralImageDisplay(QWidget):
    def __init__(self, parent=None):
        super(SpectralImageDisplay, self).__init__(parent)

        self.layout = QVBoxLayout(self)
        self.setLayout(self.layout)

        self.figure = Figure(figsize=(6, 6))
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)

        self.layout.addWidget(self.canvas)

    def setImage(self, img: np.ndarray):
        self.ax.clear()
        self.ax.imshow(img)
        self.canvas.draw()

    def createPlt(self, fileName):
        print('Creating plt...')
        sdv = SpectralDataViewer(fileName)
        self.setImage(np.array(sdv.image))