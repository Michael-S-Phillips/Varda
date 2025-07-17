from typing import Tuple

from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
import pyqtgraph as pg

import logging

from varda.utilities.wavelength_processor import WavelengthProcessor
from varda.utilities.bounds_validator import BoundsValidator
from varda.utilities.invalid_data_handler import (
    InvalidDataHandler,
    InvalidValueStrategy,
)

logger = logging.getLogger(__name__)


class PixelPlot(QWidget):
    """Separate window for displaying pixel spectrum plots."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Initialize the plot widget
        self.plotWidget: pg.PlotWidget = None
        self._initUI()

    def _initUI(self):
        self.setWindowTitle("Pixel Spectrum")
        self.plotWidget = pg.PlotWidget(title="Pixel Spectrum")
        # self.plotWidget.setMinimumSize(600, 300)
        self.plotWidget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plotWidget.addLegend()

        layout = QVBoxLayout()
        layout.addWidget(self.plotWidget)
        self.setLayout(layout)

    def plot(self, image, coords: QPointF | Tuple[int, int]):
        """Update the plot with new spectral data and comprehensive data validation."""
        self.plotWidget.clear()
        raster_data = image.raster

        # Validate coordinates before accessing pixel data
        if isinstance(coords, QPointF):
            x, y = int(coords.x()), int(coords.y())  # do we need to convert to int?
        else:
            x, y = coords
        is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
            x, y, raster_data.shape, allow_clipping=True
        )

        if not is_valid:
            logger.error(
                f"Invalid coordinates ({x}, {y}) for image with shape {raster_data.shape}"
            )
            QMessageBox.critical(
                self,
                "Invalid Coordinates",
                f"Coordinates ({x}, {y}) are outside image bounds",
            )
            return

        # Get spectral data using safe pixel access
        spectral_data = BoundsValidator.safe_pixel_access(raster_data, safe_x, safe_y)

        # Use centralized wavelength processing
        wavelengths, wavelength_type = WavelengthProcessor.process_wavelength_data(
            image.metadata.wavelengths, raster_data.shape[2]
        )

        # Handle invalid values in the spectral pair
        clean_wavelengths, clean_spectral_data, cleaning_success, cleaning_message = (
            InvalidDataHandler.handle_spectral_pair(
                wavelengths,
                spectral_data,
                strategy=InvalidValueStrategy.INTERPOLATE,
                sync_removal=False,
            )
        )

        # Validate data quality
        is_good_quality, quality_report = (
            InvalidDataHandler.validate_spectral_data_quality(
                clean_wavelengths, clean_spectral_data, min_valid_percentage=25.0
            )
        )

        # Handle data quality issues
        if not cleaning_success:
            logger.warning(f"Invalid data handling issues: {cleaning_message}")
            QMessageBox.information(
                self, "Data Processing", f"Data processing applied: {cleaning_message}"
            )

        if not is_good_quality:
            logger.warning(
                f"Data quality issues for pixel ({safe_x}, {safe_y}): {quality_report.get('quality_issues', [])}"
            )
            QMessageBox.information(
                self,
                "Data Quality Warning",
                f"Data quality issues detected:\n"
                + "\n".join(quality_report.get("quality_issues", []))
                + f"\n\nContinuing with available data...",
            )

        # Final validation
        if len(clean_spectral_data) == 0:
            logger.error(
                f"No valid spectral data available for pixel ({safe_x}, {safe_y})"
            )
            QMessageBox.critical(
                self,
                "No Data",
                f"No valid spectral data available for pixel ({safe_x}, {safe_y})",
            )
            return

        # Update plot axis label based on wavelength type
        x_label = WavelengthProcessor.get_wavelength_label(wavelength_type)
        self.plotWidget.setLabels(left="Intensity", bottom=x_label)

        # Create plot title with quality indicators
        title_base = f"Pixel Spectrum at ({safe_x}, {safe_y})"
        if not cleaning_success or not is_good_quality:
            title_base += " ⚠"  # Warning indicator

        # Log processed data information
        wavelength_info = WavelengthProcessor.format_wavelength_info(
            clean_wavelengths, wavelength_type
        )
        logger.debug(f"Plotting spectrum for coordinates: ({safe_x}, {safe_y})")
        logger.debug(f"Using wavelength range: {wavelength_info}")
        logger.debug(
            f"Spectral data range: {clean_spectral_data.min():.2f} - {clean_spectral_data.max():.2f}"
        )
        logger.debug(f"Data cleaning: {cleaning_message}")

        # Choose plot color based on data quality
        plot_color = "y"  # Default yellow
        if not is_good_quality:
            plot_color = "r"  # Red for poor quality
        elif not cleaning_success:
            plot_color = "orange"  # Orange for cleaning issues

        # Plot the spectrum
        try:
            self.plotWidget.plot(clean_wavelengths, clean_spectral_data, pen=plot_color)
            self.plotWidget.setTitle(title_base)

            if not self.isVisible():
                self.show()

            logger.info(
                f"Successfully plotted spectrum with {len(clean_wavelengths)} data points"
            )

        except Exception as e:
            logger.error(f"Failed to plot spectrum: {e}")
            QMessageBox.critical(
                self, "Plot Error", f"Failed to display spectrum: {str(e)}"
            )
