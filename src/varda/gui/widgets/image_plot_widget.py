import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint
import pyqtgraph as pg
import logging
from typing import Dict, List, Optional, Tuple, Any

from varda.core.data import ProjectContext
from varda.core.utilities.wavelength_processor import WavelengthProcessor
from varda.core.utilities.bounds_validator import BoundsValidator
from varda.core.utilities.data_converter import DataConverter
from varda.core.utilities.invalid_data_handler import (
    InvalidDataHandler,
    InvalidValueStrategy,
)

logger = logging.getLogger(__name__)


class SpectrumData:
    """Container for individual spectrum data and properties."""

    def __init__(
        self,
        spectrum_id: str,
        wavelengths: np.ndarray,
        values: np.ndarray,
        label: str,
        color: str = "blue",
        line_width: int = 1,
        marker_symbol: Optional[str] = None,
        marker_size: int = 5,
        visible: bool = True,
        coords: Optional[Tuple[int, int]] = None,
        image_index: Optional[int] = None,
        wavelength_type: str = "numeric",  # wavelength type tracking
    ):
        self.spectrum_id = spectrum_id
        self.wavelengths = np.asarray(wavelengths, dtype=float)
        self.values = np.asarray(values, dtype=float)
        self.label = label
        self.color = color
        self.line_width = line_width
        self.marker_symbol = marker_symbol
        self.marker_size = marker_size
        self.visible = visible
        self.coords = coords
        self.image_index = image_index
        self.wavelength_type = wavelength_type

        # PyQtGraph plot item reference
        self.plot_item = None

    def get_pen(self):
        """Get PyQtGraph pen object for this spectrum."""
        return pg.mkPen(color=self.color, width=self.line_width)

    def get_symbol_brush(self):
        """Get PyQtGraph brush for markers."""
        return pg.mkBrush(color=self.color) if self.marker_symbol else None


class ImagePlotWidget(QWidget):
    """
    Widget for plotting spectral data from images.
    Supports multiple spectra on the same plot with individual properties.
    Can be used as embedded widget or popup window.
    """

    sigClicked = pyqtSignal()
    sigSpectrumAdded = pyqtSignal(str)  # spectrum_id
    sigSpectrumRemoved = pyqtSignal(str)  # spectrum_id
    sigSpectrumUpdated = pyqtSignal(str)  # spectrum_id

    _pressPos = None

    def __init__(
        self,
        proj: ProjectContext = None,
        imageIndex=None,
        isWindow: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.isWindow = isWindow
        self.proj = proj
        self.imageIndex = imageIndex

        # Storage for multiple spectra
        self.spectra: Dict[str, SpectrumData] = {}
        self.spectrum_counter = 0

        # Default colors for new spectra
        self.default_colors = [
            "blue",
            "red",
            "green",
            "orange",
            "purple",
            "brown",
            "pink",
            "gray",
            "olive",
            "cyan",
            "magenta",
            "yellow",
        ]

        self._init_ui()
        self._setup_event_handling()

        # Auto-set image if provided
        if self.proj is not None and self.imageIndex is not None:
            self.setImage(self.imageIndex)

        logger.debug("ImagePlotWidget initialized")

    def _init_ui(self):
        """Initialize the user interface."""
        # Configure window properties
        if self.isWindow:
            self.setWindowTitle("Spectral Plot")
            self.setMinimumSize(600, 400)
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setMinimumHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        # Initialize plot widget
        self.plot_widget = pg.PlotWidget(title="Spectral Plot")
        self.plot_widget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()

        # Create layout
        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

        self.show()

    def _setup_event_handling(self):
        """Set up event handling for the plot widget."""
        scene = self.plot_widget.getViewBox().scene()
        scene.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Filter events for the plot widget to handle clicks and mouse releases."""
        if event.type() == QEvent.Type.GraphicsSceneMousePress:
            self._pressPos = event.scenePos()
            logger.debug("Mouse press event")

        elif event.type() == QEvent.Type.GraphicsSceneMouseRelease:
            logger.debug("Mouse release event")
            if (
                QPoint(event.scenePos().toPoint()) - self._pressPos.toPoint()
            ).manhattanLength() < 5:
                logger.debug("ImagePlotWidget clicked!")
                self.sigClicked.emit()
            else:
                logger.debug("Mouse release was a drag, not a click.")

        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """Handle the window close event."""
        logger.debug("ImagePlotWidget closed")
        event.accept()

    def setImage(self, imageIndex):
        """Set the image index for the plot widget."""
        self.imageIndex = imageIndex
        if self.proj:
            image = self.proj.getImage(imageIndex)
            self.setWindowTitle(f"Spectral Plot - {image.metadata.name}")

    def add_spectrum(
        self,
        wavelengths: np.ndarray,
        values: np.ndarray,
        label: str = None,
        spectrum_id: str = None,
        color: str = None,
        coords: Optional[Tuple[int, int]] = None,
        image_index: Optional[int] = None,
        wavelength_type: str = "numeric",
        **kwargs,
    ) -> str:
        """
        Add a new spectrum to the plot with comprehensive validation and invalid data handling.
        """
        try:
            # First, handle invalid values in the spectral pair
            clean_wavelengths, clean_values, cleaning_success, cleaning_message = (
                InvalidDataHandler.handle_spectral_pair(
                    wavelengths,
                    values,
                    strategy=InvalidValueStrategy.INTERPOLATE,
                    sync_removal=False,
                )
            )

            # Then apply data converter for additional validation
            wavelengths_converted, wavelengths_success, wavelengths_error = (
                DataConverter.safe_array_conversion(
                    clean_wavelengths,
                    target_dtype=float,
                    fallback_strategy="interpolate",
                )
            )

            values_converted, values_success, values_error = (
                DataConverter.safe_array_conversion(
                    clean_values,
                    target_dtype=float,
                    fallback_strategy="zeros",
                    expected_length=len(wavelengths_converted),
                )
            )

            # Validate data quality
            is_good_quality, quality_report = (
                InvalidDataHandler.validate_spectral_data_quality(
                    wavelengths_converted, values_converted, min_valid_percentage=30.0
                )
            )

            # Check for critical failures
            if not wavelengths_success and not values_success:
                raise ValueError("Both wavelength and spectral data processing failed")

            if len(wavelengths_converted) == 0 or len(values_converted) == 0:
                raise ValueError("No valid data points available for plotting")

            # Generate ID and label if not provided
            if spectrum_id is None:
                spectrum_id = f"spectrum_{self.spectrum_counter}"
                self.spectrum_counter += 1

            if label is None:
                if coords:
                    label = f"Pixel ({coords[0]}, {coords[1]})"
                else:
                    label = f"Spectrum {self.spectrum_counter}"

            # Auto-assign color if not provided
            if color is None:
                color_index = len(self.spectra) % len(self.default_colors)
                color = self.default_colors[color_index]

            # Create spectrum data object with validated data
            spectrum = SpectrumData(
                spectrum_id=spectrum_id,
                wavelengths=wavelengths_converted,
                values=values_converted,
                label=label,
                color=color,
                coords=coords,
                image_index=image_index,
                wavelength_type=wavelength_type,
                **kwargs,
            )

            # Store spectrum
            self.spectra[spectrum_id] = spectrum

            # Add to plot
            self._add_spectrum_to_plot(spectrum)

            # Update plot title
            if len(self.spectra) == 1:
                self.plot_widget.setTitle(f"Spectral Plot - {label}")
            else:
                self.plot_widget.setTitle(
                    f"Spectral Plot - {len(self.spectra)} spectra"
                )

            # Log any data quality issues
            if not cleaning_success:
                logger.warning(
                    f"Invalid data handling for spectrum {spectrum_id}: {cleaning_message}"
                )
            if not wavelengths_success:
                logger.warning(
                    f"Wavelength conversion issues for spectrum {spectrum_id}: {wavelengths_error}"
                )
            if not values_success:
                logger.warning(
                    f"Values conversion issues for spectrum {spectrum_id}: {values_error}"
                )
            if not is_good_quality:
                logger.warning(
                    f"Data quality issues for spectrum {spectrum_id}: {quality_report.get('quality_issues', [])}"
                )

            self.sigSpectrumAdded.emit(spectrum_id)
            logger.debug(
                f"Added spectrum: {spectrum_id} ({label}) with {len(wavelengths_converted)} data points"
            )

            return spectrum_id

        except Exception as e:
            logger.error(f"Failed to add spectrum: {e}")
            raise ValueError(f"Cannot add spectrum: {str(e)}")

    def _add_spectrum_to_plot(self, spectrum: SpectrumData):
        """Add a spectrum to the PyQtGraph plot with error handling."""
        try:
            if not spectrum.visible:
                return

            # Validate data before plotting
            if len(spectrum.wavelengths) == 0 or len(spectrum.values) == 0:
                logger.error(
                    f"Cannot plot spectrum {spectrum.spectrum_id}: empty data arrays"
                )
                return

            if len(spectrum.wavelengths) != len(spectrum.values):
                logger.error(
                    f"Cannot plot spectrum {spectrum.spectrum_id}: "
                    f"wavelength and value array length mismatch"
                )
                return

            # Check for valid data ranges
            if np.all(np.isnan(spectrum.values)) or np.all(np.isinf(spectrum.values)):
                logger.warning(
                    f"Spectrum {spectrum.spectrum_id} contains only invalid values"
                )
                return

            # Create plot arguments
            plot_args = {"pen": spectrum.get_pen(), "name": spectrum.label}

            # Add markers if specified
            if spectrum.marker_symbol:
                plot_args["symbol"] = spectrum.marker_symbol
                plot_args["symbolSize"] = spectrum.marker_size
                plot_args["symbolBrush"] = spectrum.get_symbol_brush()

            # Add to plot and store reference
            spectrum.plot_item = self.plot_widget.plot(
                spectrum.wavelengths, spectrum.values, **plot_args
            )

            logger.debug(f"Successfully added spectrum {spectrum.spectrum_id} to plot")

        except Exception as e:
            logger.error(f"Error adding spectrum {spectrum.spectrum_id} to plot: {e}")
            # Don't raise exception to prevent breaking the entire plotting process
            spectrum.plot_item = None

    def remove_spectrum(self, spectrum_id: str) -> bool:
        """
        Remove a spectrum from the plot.

        Args:
            spectrum_id: ID of spectrum to remove

        Returns:
            bool: True if spectrum was found and removed
        """
        if spectrum_id not in self.spectra:
            logger.warning(f"Spectrum {spectrum_id} not found")
            return False

        spectrum = self.spectra[spectrum_id]

        # Remove from plot
        if spectrum.plot_item:
            self.plot_widget.removeItem(spectrum.plot_item)

        # Remove from storage
        del self.spectra[spectrum_id]

        # Update plot title
        if len(self.spectra) == 0:
            self.plot_widget.setTitle("Spectral Plot")
        elif len(self.spectra) == 1:
            remaining = next(iter(self.spectra.values()))
            self.plot_widget.setTitle(f"Spectral Plot - {remaining.label}")
        else:
            self.plot_widget.setTitle(f"Spectral Plot - {len(self.spectra)} spectra")

        self.sigSpectrumRemoved.emit(spectrum_id)
        logger.debug(f"Removed spectrum: {spectrum_id}")

        return True

    def update_spectrum_properties(self, spectrum_id: str, **properties) -> bool:
        """
        Update properties of an existing spectrum.

        Args:
            spectrum_id: ID of spectrum to update
            **properties: Properties to update (color, line_width, etc.)

        Returns:
            bool: True if spectrum was found and updated
        """
        if spectrum_id not in self.spectra:
            logger.warning(f"Spectrum {spectrum_id} not found")
            return False

        spectrum = self.spectra[spectrum_id]

        # Update properties
        for key, value in properties.items():
            if hasattr(spectrum, key):
                setattr(spectrum, key, value)

        # Remove old plot item
        if spectrum.plot_item:
            self.plot_widget.removeItem(spectrum.plot_item)
            spectrum.plot_item = None

        # Re-add with new properties
        self._add_spectrum_to_plot(spectrum)

        self.sigSpectrumUpdated.emit(spectrum_id)
        logger.debug(f"Updated spectrum properties: {spectrum_id}")

        return True

    def set_spectrum_visibility(self, spectrum_id: str, visible: bool) -> bool:
        """
        Show or hide a spectrum.

        Args:
            spectrum_id: ID of spectrum
            visible: Whether spectrum should be visible

        Returns:
            bool: True if spectrum was found and updated
        """
        if spectrum_id not in self.spectra:
            return False

        spectrum = self.spectra[spectrum_id]
        spectrum.visible = visible

        if visible:
            # Add to plot if not already there
            if not spectrum.plot_item:
                self._add_spectrum_to_plot(spectrum)
        else:
            # Remove from plot
            if spectrum.plot_item:
                self.plot_widget.removeItem(spectrum.plot_item)
                spectrum.plot_item = None

        return True

    def clear_all_spectra(self):
        """Remove all spectra from the plot."""
        for spectrum_id in list(self.spectra.keys()):
            self.remove_spectrum(spectrum_id)

    def get_spectrum_ids(self) -> List[str]:
        """Get list of all spectrum IDs."""
        return list(self.spectra.keys())

    def get_spectrum_info(self, spectrum_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a spectrum.

        Args:
            spectrum_id: ID of spectrum

        Returns:
            dict: Spectrum information or None if not found
        """
        if spectrum_id not in self.spectra:
            return None

        spectrum = self.spectra[spectrum_id]
        return {
            "spectrum_id": spectrum.spectrum_id,
            "label": spectrum.label,
            "color": spectrum.color,
            "line_width": spectrum.line_width,
            "marker_symbol": spectrum.marker_symbol,
            "marker_size": spectrum.marker_size,
            "visible": spectrum.visible,
            "coords": spectrum.coords,
            "image_index": spectrum.image_index,
            "data_points": len(spectrum.wavelengths),
        }

    def get_all_spectra_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all spectra."""
        return {sid: self.get_spectrum_info(sid) for sid in self.spectra.keys()}

    def set_legend_visible(self, visible: bool):
        """Show or hide the plot legend."""
        legend = self.plot_widget.getPlotItem().legend
        if legend:
            legend.setVisible(visible)

    # Legacy compatibility methods
    def showPixelSpectrum(self, x: int, y: int, imageIndex: Optional[int] = None):
        """
        Legacy method for backward compatibility.
        Adds a single pixel spectrum to the plot with comprehensive data validation.
        """
        if imageIndex is not None:
            self.setImage(imageIndex)

        if not self.proj:
            logger.error("No project context available")
            return

        image = self.proj.getImage(self.imageIndex)

        # Validate coordinates before accessing pixel data
        is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
            x, y, image.raster.shape, allow_clipping=True
        )

        if not is_valid:
            logger.error(
                f"Invalid coordinates ({x}, {y}) for image with shape {image.raster.shape}"
            )
            return

        # Use centralized wavelength processing
        wavelengths, wavelength_type = WavelengthProcessor.process_wavelength_data(
            image.metadata.wavelengths, image.raster.shape[2]
        )

        # Get spectrum using safe pixel access
        spectrum = BoundsValidator.safe_pixel_access(image.raster, safe_x, safe_y)

        # Handle invalid values in the spectral pair
        clean_wavelengths, clean_spectrum, cleaning_success, cleaning_message = (
            InvalidDataHandler.handle_spectral_pair(
                wavelengths,
                spectrum,
                strategy=InvalidValueStrategy.INTERPOLATE,
                sync_removal=False,
            )
        )

        # Validate data quality
        is_good_quality, quality_report = (
            InvalidDataHandler.validate_spectral_data_quality(
                clean_wavelengths,
                clean_spectrum,
                min_valid_percentage=25.0,  # Allow lower threshold for single pixels
            )
        )

        # Log data quality information
        if not cleaning_success:
            logger.warning(f"Data cleaning issues: {cleaning_message}")

        if not is_good_quality:
            logger.warning(
                f"Data quality issues for pixel ({safe_x}, {safe_y}): {quality_report.get('quality_issues', [])}"
            )
            # Show warning but continue with plot
            QMessageBox.information(
                self,
                "Data Quality Warning",
                f"Spectral data quality issues detected:\n"
                + "\n".join(quality_report.get("quality_issues", []))
                + f"\n\nData cleaning: {cleaning_message}",
            )

        # Update plot axis label based on wavelength type
        x_label = WavelengthProcessor.get_wavelength_label(wavelength_type)
        self.plot_widget.setLabels(bottom=x_label)

        # Log processed data information
        wavelength_info = WavelengthProcessor.format_wavelength_info(
            clean_wavelengths, wavelength_type
        )
        logger.debug(f"Using wavelength range: {wavelength_info}")
        logger.debug(f"Data cleaning: {cleaning_message}")

        # Validate final spectrum data
        if len(clean_spectrum) == 0:
            logger.error(
                f"No valid spectral data available for pixel ({safe_x}, {safe_y})"
            )
            QMessageBox.critical(
                self,
                "No Data",
                f"No valid spectral data available for pixel ({safe_x}, {safe_y})",
            )
            return

        # Add to plot (replaces existing single spectrum)
        self.clear_all_spectra()

        # Create label with data quality indicator
        base_label = f"({safe_x}, {safe_y})"
        if not cleaning_success or not is_good_quality:
            base_label += " ⚠"  # Warning indicator

        self.add_spectrum(
            wavelengths=clean_wavelengths,
            values=clean_spectrum,
            coords=(safe_x, safe_y),
            image_index=self.imageIndex,
            wavelength_type=wavelength_type,
            label=base_label,
        )

    def updatePlot(self, wavelengths: np.ndarray, spectrum: np.ndarray, coords):
        """
        Legacy method for backward compatibility.
        Updates plot with single spectrum data with comprehensive error and invalid data handling.
        """
        # Safe data conversion with comprehensive error handling
        wavelengths_converted, wavelengths_success, wavelengths_error = (
            DataConverter.safe_array_conversion(
                wavelengths, target_dtype=float, fallback_strategy="interpolate"
            )
        )

        spectrum_converted, spectrum_success, spectrum_error = (
            DataConverter.safe_array_conversion(
                spectrum,
                target_dtype=float,
                fallback_strategy="zeros",
                expected_length=(
                    len(wavelengths_converted) if wavelengths_success else None
                ),
            )
        )

        # Handle invalid values in the spectral pair
        clean_wavelengths, clean_spectrum, cleaning_success, cleaning_message = (
            InvalidDataHandler.handle_spectral_pair(
                wavelengths_converted,
                spectrum_converted,
                strategy=InvalidValueStrategy.INTERPOLATE,
                sync_removal=False,
            )
        )

        # Validate data quality
        is_good_quality, quality_report = (
            InvalidDataHandler.validate_spectral_data_quality(
                clean_wavelengths, clean_spectrum, min_valid_percentage=50.0
            )
        )

        # Handle various failure scenarios
        if not wavelengths_success or not spectrum_success:
            logger.error("Data conversion failed")
            error_details = []
            if not wavelengths_success:
                error_details.append(f"Wavelength: {wavelengths_error}")
            if not spectrum_success:
                error_details.append(f"Spectrum: {spectrum_error}")

            QMessageBox.warning(
                self,
                "Data Conversion Error",
                f"Failed to convert data:\n"
                + "\n".join(error_details)
                + f"\n\nAttempting to continue with recovered data...",
            )

        if not cleaning_success:
            logger.warning(f"Invalid data handling issues: {cleaning_message}")

        if not is_good_quality:
            logger.warning(
                f"Data quality issues: {quality_report.get('quality_issues', [])}"
            )
            QMessageBox.information(
                self,
                "Data Quality Warning",
                f"Data quality issues detected:\n"
                + "\n".join(quality_report.get("quality_issues", []))
                + f"\n\nContinuing with available data...",
            )

        # Final validation
        if len(clean_wavelengths) == 0 or len(clean_spectrum) == 0:
            QMessageBox.critical(
                self, "No Valid Data", "No valid spectral data available for plotting."
            )
            return

        # Log successful data information
        logger.debug(f"Plotting spectrum for coordinates: {coords}")
        logger.debug(
            f"Wavelength range: {clean_wavelengths.min():.2f} - {clean_wavelengths.max():.2f}"
        )
        logger.debug(
            f"Spectral data range: {clean_spectrum.min():.2f} - {clean_spectrum.max():.2f}"
        )
        logger.debug(f"Data points: {len(clean_wavelengths)}")
        logger.debug(f"Data cleaning: {cleaning_message}")

        # Clear existing and add new spectrum
        self.clear_all_spectra()

        # Format coordinate label with quality indicators
        if isinstance(coords, tuple) and len(coords) == 2:
            label = f"({coords[0]}, {coords[1]})"
            coord_tuple = coords
        else:
            label = str(coords)
            coord_tuple = None

        # Add quality indicators to label
        quality_indicators = []
        if not wavelengths_success or not spectrum_success:
            quality_indicators.append("recovered")
        if not cleaning_success:
            quality_indicators.append("cleaned")
        if not is_good_quality:
            quality_indicators.append("⚠")

        if quality_indicators:
            label += f" ({', '.join(quality_indicators)})"

        try:
            spectrum_id = self.add_spectrum(
                wavelengths=clean_wavelengths,
                values=clean_spectrum,
                label=label,
                coords=coord_tuple,
            )

            # Update plot styling based on data quality
            if not is_good_quality or not cleaning_success:
                # Use different styling for problematic data
                if not is_good_quality:
                    color = "red"  # Red for poor quality
                elif not cleaning_success:
                    color = "orange"  # Orange for cleaning issues
                else:
                    color = "yellow"  # Yellow for other issues

                self.update_spectrum_properties(spectrum_id, color=color, line_width=2)

            logger.info(
                f"Successfully plotted spectrum with {len(clean_wavelengths)} data points"
            )

        except Exception as e:
            logger.error(f"Failed to add spectrum to plot: {e}")
            QMessageBox.critical(
                self, "Plot Error", f"Failed to display spectrum: {str(e)}"
            )
