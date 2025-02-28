from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np

import logging

from core.data import ProjectContext

logger = logging.getLogger(__name__)


class PixelPlot(QWidget):
    """Separate window for displaying pixel spectrum plots."""

    def __init__(self, proj: ProjectContext, parent=None):
        self.proj = proj
        super().__init__(parent)
        # Initialize the plot widget
        self.plotWidget: pg.PlotWidget = None
        self._initUI()

    def _initUI(self):
        self.setWindowTitle("Pixel Spectrum")
        self.plotWidget = pg.PlotWidget(title="Pixel Spectrum")
        #self.plotWidget.setMinimumSize(600, 300)
        self.plotWidget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plotWidget.addLegend()

        layout = QVBoxLayout()
        layout.addWidget(self.plotWidget)
        self.setLayout(layout)

    def plot(self, index, coords):
        """Update the plot with new spectral data."""
        self.plotWidget.clear()
        image = self.proj.getImage(index)
        raster_data = image.raster
        spectral_data = raster_data[coords[1], coords[0], :]

        wavelengths = image.metadata.wavelength
        if wavelengths is None or len(wavelengths) == 0 or len(wavelengths) != raster_data.shape[2]:
            logger.warning(f"Invalid wavelength data detected. Using band numbers instead.")
            wavelengths = np.arange(raster_data.shape[2])
        else:
            logger.info(f"Using wavelength range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")

        logger.debug(f"Plotting spectrum for coordinates: {coords}")
        logger.debug(f"Wavelength range: {wavelengths.min():.2f} - {wavelengths.max():.2f} nm")
        logger.debug(f"Spectral data range: {spectral_data.min():.2f} - {spectral_data.max():.2f}")

        self.plotWidget.plot(wavelengths, spectral_data, pen='y')
        self.plotWidget.setTitle(f"Pixel Spectrum at ({coords[0]}, {coords[1]})")
        if not self.isVisible():
            self.show()