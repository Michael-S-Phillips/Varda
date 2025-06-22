import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint
import pyqtgraph as pg
import logging
from typing import Dict, List, Optional, Tuple, Any

from varda.core.data import ProjectContext

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
        image_index: Optional[int] = None
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
            "blue", "red", "green", "orange", "purple", "brown", 
            "pink", "gray", "olive", "cyan", "magenta", "yellow"
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
        **kwargs
    ) -> str:
        """
        Add a new spectrum to the plot.
        
        Args:
            wavelengths: Wavelength data array
            values: Spectral intensity values
            label: Display label for the spectrum
            spectrum_id: Unique identifier (auto-generated if None)
            color: Line color (auto-assigned if None)
            coords: Source pixel coordinates (x, y)
            image_index: Source image index
            **kwargs: Additional spectrum properties
            
        Returns:
            str: The spectrum ID
        """
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
        
        # Create spectrum data object
        spectrum = SpectrumData(
            spectrum_id=spectrum_id,
            wavelengths=wavelengths,
            values=values,
            label=label,
            color=color,
            coords=coords,
            image_index=image_index,
            **kwargs
        )
        
        # Store spectrum
        self.spectra[spectrum_id] = spectrum
        
        # Add to plot
        self._add_spectrum_to_plot(spectrum)
        
        # Update plot title if this is the first spectrum
        if len(self.spectra) == 1:
            self.plot_widget.setTitle(f"Spectral Plot - {label}")
        else:
            self.plot_widget.setTitle(f"Spectral Plot - {len(self.spectra)} spectra")
        
        self.sigSpectrumAdded.emit(spectrum_id)
        logger.debug(f"Added spectrum: {spectrum_id} ({label})")
        
        return spectrum_id

    def _add_spectrum_to_plot(self, spectrum: SpectrumData):
        """Add a spectrum to the PyQtGraph plot."""
        if not spectrum.visible:
            return
            
        # Create plot arguments
        plot_args = {
            'pen': spectrum.get_pen(),
            'name': spectrum.label
        }
        
        # Add markers if specified
        if spectrum.marker_symbol:
            plot_args['symbol'] = spectrum.marker_symbol
            plot_args['symbolSize'] = spectrum.marker_size
            plot_args['symbolBrush'] = spectrum.get_symbol_brush()
        
        # Add to plot and store reference
        spectrum.plot_item = self.plot_widget.plot(
            spectrum.wavelengths, 
            spectrum.values,
            **plot_args
        )

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
            'spectrum_id': spectrum.spectrum_id,
            'label': spectrum.label,
            'color': spectrum.color,
            'line_width': spectrum.line_width,
            'marker_symbol': spectrum.marker_symbol,
            'marker_size': spectrum.marker_size,
            'visible': spectrum.visible,
            'coords': spectrum.coords,
            'image_index': spectrum.image_index,
            'data_points': len(spectrum.wavelengths)
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
        Adds a single pixel spectrum to the plot.
        """
        if imageIndex is not None:
            self.setImage(imageIndex)

        if not self.proj:
            logger.error("No project context available")
            return

        image = self.proj.getImage(self.imageIndex)

        # Get wavelengths
        try:
            wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(float)
        except ValueError:
            logger.warning("Wavelengths appear to be categorical. Using band numbers.")
            wavelengths = np.arange(len(image.metadata.wavelengths), dtype=float)

        # Get spectrum
        spectrum = image.raster[y, x, :]
        
        # Add to plot (replaces existing single spectrum)
        self.clear_all_spectra()
        self.add_spectrum(
            wavelengths=wavelengths,
            values=spectrum,
            coords=(x, y),
            image_index=self.imageIndex
        )

    def updatePlot(self, wavelengths: np.ndarray, spectrum: np.ndarray, coords):
        """
        Legacy method for backward compatibility.
        Updates plot with single spectrum data.
        """
        try:
            wavelengths = np.asarray(wavelengths, dtype=float)
            spectrum = np.asarray(spectrum, dtype=float)
            
            logger.debug(f"Plotting spectrum for coordinates: {coords}")
            logger.debug(
                f"Wavelength range: {wavelengths.min() if len(wavelengths) > 0 else 'N/A'} - "
                + f"{wavelengths.max() if len(wavelengths) > 0 else 'N/A'} nm"
            )
            logger.debug(
                f"Spectral data range: {spectrum.min() if len(spectrum) > 0 else 'N/A'} - "
                + f"{spectrum.max() if len(spectrum) > 0 else 'N/A'}"
            )
        except ValueError as e:
            logger.error(f"Error converting data to numeric types: {e}")
            return

        # Clear existing and add new spectrum
        self.clear_all_spectra()
        
        if isinstance(coords, tuple) and len(coords) == 2:
            label = f"({coords[0]}, {coords[1]})"
            coord_tuple = coords
        else:
            label = str(coords)
            coord_tuple = None
        
        self.add_spectrum(
            wavelengths=wavelengths,
            values=spectrum,
            label=label,
            coords=coord_tuple
        )