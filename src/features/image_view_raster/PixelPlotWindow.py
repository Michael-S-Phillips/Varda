import numpy as np
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt
import pyqtgraph as pg

class PixelPlotWindow(QMainWindow):
    """
    A pop-up window for displaying a large pixel spectrum plot.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pixel Spectrum")
        self.setMinimumSize(600, 300)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.plot_widget = pg.PlotWidget(title="Pixel Spectrum")
        self.plot_widget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()

        self.setCentralWidget(self.plot_widget)
        self.hide()

    def update_plot(self, wavelengths, spectrum, coords):
        self.plot_widget.clear()
        self.plot_widget.plot(wavelengths, spectrum, pen='y', name=f"({coords[0]}, {coords[1]})")
        self.plot_widget.setTitle(f"Pixel Spectrum at {coords}")
