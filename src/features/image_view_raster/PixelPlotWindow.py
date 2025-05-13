import numpy as np
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import logging

logger = logging.getLogger(__name__)

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
        
        logger.debug("PixelPlotWindow initialized")
        
    def closeEvent(self, event):
        """Handle the window close event."""
        logger.debug("PixelPlotWindow closed")
        # Ensure window is properly closed and removed from tracking
        event.accept()

    def update_plot(self, wavelengths, spectrum, coords):
        """Update the plot with new spectral data."""
        self.plot_widget.clear()
        logger.debug(f"Plotting spectrum for coordinates: {coords}")
        try:
            try:
                wavelengths = np.asarray(wavelengths, dtype=float)
            except ValueError as e:
                logger.warning(f"Wavelengths appear to be categorical. Generating a numeric vector of the same length.")
                wavelengths = np.arange(len(wavelengths), dtype=float)
            spectrum = np.asarray(spectrum, dtype=float)
            logger.debug(f"Wavelength range: {wavelengths.min() if len(wavelengths) > 0 else 'N/A'} - " + 
                        f"{wavelengths.max() if len(wavelengths) > 0 else 'N/A'} nm")
            logger.debug(f"Spectral data range: {spectrum.min() if len(spectrum) > 0 else 'N/A'} - " + 
                        f"{spectrum.max() if len(spectrum) > 0 else 'N/A'}")
        except ValueError as e:
            logger.error(f"Error converting data to numeric types: {e}")
            return

        self.plot_widget.plot(wavelengths, spectrum, pen='y', name=f"({coords[0]}, {coords[1]})")
        self.plot_widget.setTitle(f"Pixel Spectrum at {coords}")