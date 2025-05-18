import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg

class PixelPlotWidget(QWidget):
    """
    A small embedded widget that shows a live pixel spectrum.
    Emits `clicked` when the user clicks it to open a popup.
    """
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(180)

        self.plot = pg.PlotWidget(title="Pixel Spectrum")
        self.plot.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plot.showGrid(x=True, y=True)

        layout = QVBoxLayout()
        layout.addWidget(self.plot)
        self.setLayout(layout)

    def update_plot(self, wavelengths, spectrum, coords):
        self.plot.clear()
        self.plot.plot(wavelengths, spectrum, pen='y', name=f"({coords[0]}, {coords[1]})")
        self.plot.setTitle(f"Pixel Spectrum at {coords}")

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)
