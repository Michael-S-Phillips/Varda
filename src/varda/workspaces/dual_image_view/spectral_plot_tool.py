"""
Spectral Plot Tool for Dual Image View

Enables spectral plotting from clicks on either image in dual view mode.
Users can select which image to extract spectral data from.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QCheckBox,
    QSpinBox,
    QGroupBox,
    QButtonGroup,
    QRadioButton,
)

from varda.project import ProjectContext
from varda.common._old_widgets.image_plot_widget import ImagePlotWidget
from .dual_image_tool_base import DualImageToolBase, DualImageToolPanel

logger = logging.getLogger(__name__)


class SpectralPlotToolPanel(DualImageToolPanel):
    """UI panel for spectral plot tool controls"""

    # Signals
    spectral_source_changed = pyqtSignal(str)  # 'primary' or 'secondary'
    plot_mode_changed = pyqtSignal(str)  # 'overlay' or 'accumulate'
    clear_spectra_requested = pyqtSignal()
    auto_label_toggled = pyqtSignal(bool)
    max_spectra_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__("Spectral Plot", parent)
        self._setup_controls()
        self._connect_signals()

    def _setup_controls(self):
        """Setup the tool-specific controls"""

        # Source selection group
        source_group = QGroupBox("Spectral Data Source")
        source_layout = QVBoxLayout(source_group)

        self.source_button_group = QButtonGroup(self)

        self.primary_radio = QRadioButton("Primary Image")
        self.primary_radio.setToolTip("Extract spectra from the primary image")
        self.primary_radio.setChecked(True)
        self.source_button_group.addButton(self.primary_radio, 0)
        source_layout.addWidget(self.primary_radio)

        self.secondary_radio = QRadioButton("Secondary Image")
        self.secondary_radio.setToolTip("Extract spectra from the secondary image")
        self.source_button_group.addButton(self.secondary_radio, 1)
        source_layout.addWidget(self.secondary_radio)

        self.add_content_widget(source_group)

        # Plot behavior group
        behavior_group = QGroupBox("Plot Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        # Plot mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Overlay Spectra", "overlay")
        self.mode_combo.addItem("Replace Previous", "replace")
        self.mode_combo.addItem("Accumulate All", "accumulate")
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.setToolTip("Choose how new spectra are displayed")
        mode_layout.addWidget(self.mode_combo)
        mode_layout.addStretch()

        behavior_layout.addLayout(mode_layout)

        # Auto-labeling
        self.auto_label_cb = QCheckBox("Auto-label with coordinates")
        self.auto_label_cb.setChecked(True)
        self.auto_label_cb.setToolTip(
            "Automatically label spectra with their image coordinates"
        )
        behavior_layout.addWidget(self.auto_label_cb)

        # Max spectra limit
        max_layout = QHBoxLayout()
        max_layout.addWidget(QLabel("Max spectra:"))

        self.max_spectra_spin = QSpinBox()
        self.max_spectra_spin.setRange(1, 50)
        self.max_spectra_spin.setValue(10)
        self.max_spectra_spin.setToolTip("Maximum number of spectra to keep on plot")
        max_layout.addWidget(self.max_spectra_spin)
        max_layout.addStretch()

        behavior_layout.addLayout(max_layout)

        self.add_content_widget(behavior_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.clear_button = QPushButton("Clear All Spectra")
        self.clear_button.setToolTip("Remove all spectra from the plot")
        button_layout.addWidget(self.clear_button)

        button_layout.addStretch()

        self.add_content_layout(button_layout)

    def _connect_signals(self):
        """Connect control signals"""
        self.source_button_group.idToggled.connect(self._on_source_changed)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_combo_changed)
        self.clear_button.clicked.connect(self.clear_spectra_requested.emit)
        self.auto_label_cb.toggled.connect(self.auto_label_toggled.emit)
        self.max_spectra_spin.valueChanged.connect(self.max_spectra_changed.emit)

    def _on_source_changed(self, button_id: int, checked: bool):
        """Handle source radio button changes"""
        if checked:
            source = "primary" if button_id == 0 else "secondary"
            self.spectral_source_changed.emit(source)

    def _on_mode_combo_changed(self, index: int):
        """Handle mode combo box changes"""
        mode_data = self.mode_combo.itemData(index)
        if mode_data:
            self.plot_mode_changed.emit(mode_data)

    def get_spectral_source(self) -> str:
        """Get the currently selected spectral data source"""
        return "primary" if self.primary_radio.isChecked() else "secondary"

    def get_plot_mode(self) -> str:
        """Get the currently selected plot mode"""
        current_index = self.mode_combo.currentIndex()
        return self.mode_combo.itemData(current_index) or "overlay"

    def get_auto_label(self) -> bool:
        """Get auto-label setting"""
        return self.auto_label_cb.isChecked()

    def get_max_spectra(self) -> int:
        """Get maximum spectra setting"""
        return self.max_spectra_spin.value()


class SpectralPlotTool(DualImageToolBase):
    """
    Tool for extracting and plotting spectra from dual image views.

    Allows users to click on either image and extract spectral data
    from the selected source image for plotting.
    """

    def __init__(self, tool_name: str, project_context: ProjectContext, parent=None):
        super().__init__(tool_name, project_context, parent)

        # Tool state
        self._spectral_source = "primary"  # 'primary' or 'secondary'
        self._plot_mode = "overlay"  # 'overlay', 'replace', or 'accumulate'
        self._auto_label = True
        self._max_spectra = 10
        self._spectrum_counter = 0

        # UI components
        self._control_panel: Optional[SpectralPlotToolPanel] = None
        self._plot_widget: Optional[ImagePlotWidget] = None

    def _create_ui(self) -> QWidget:
        """Create the tool's UI widget"""
        try:
            logger.debug("SpectralPlotTool: Creating UI widget")

            # Main container
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(5)

            # Control panel
            logger.debug("SpectralPlotTool: Creating control panel")
            self._control_panel = SpectralPlotToolPanel()
            layout.addWidget(self._control_panel)

            # Plot widget
            logger.debug("SpectralPlotTool: Creating plot widget")
            self._plot_widget = ImagePlotWidget(
                proj=self.proj, imageIndex=None, isWindow=False
            )
            self._plot_widget.setMinimumHeight(200)
            layout.addWidget(self._plot_widget)

            # Connect control panel signals
            logger.debug("SpectralPlotTool: Connecting control signals")
            self._connect_control_signals()

            logger.debug("SpectralPlotTool: UI creation completed successfully")
            return container

        except Exception as e:
            logger.error(f"Error creating SpectralPlotTool UI: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return a simple widget as fallback
            fallback = QWidget()
            fallback_layout = QVBoxLayout(fallback)
            fallback_layout.addWidget(QLabel(f"Error creating tool UI: {str(e)}"))
            return fallback

    def _connect_control_signals(self):
        """Connect signals from the control panel"""
        if self._control_panel:
            self._control_panel.spectral_source_changed.connect(self._on_source_changed)
            self._control_panel.plot_mode_changed.connect(self._on_plot_mode_changed)
            self._control_panel.clear_spectra_requested.connect(self._on_clear_spectra)
            self._control_panel.auto_label_toggled.connect(self._on_auto_label_toggled)
            self._control_panel.max_spectra_changed.connect(
                self._on_max_spectra_changed
            )

    def _on_activate(self) -> bool:
        """Handle tool activation"""
        if self._plot_widget:
            # Clear any existing spectra
            self._plot_widget.clear_all_spectra()
            self._spectrum_counter = 0

        self.status_changed.emit(
            self.tool_name, "Ready - Click on images to plot spectra"
        )
        return True

    def _on_deactivate(self) -> bool:
        """Handle tool deactivation"""
        self.status_changed.emit(self.tool_name, "Deactivated")
        return True

    def _on_click(self, image_index: int, x: int, y: int, view_type: str) -> bool:
        """Handle click events to extract and plot spectra"""
        if not self._plot_widget:
            return False

        # Determine which image to extract spectral data from
        source_index = self._get_source_image_index()
        if source_index is None:
            logger.error("No valid source image index available")
            return False

        try:
            # Get the source image
            source_image = self.proj.getImage(source_index)

            # Validate coordinates for the source image
            from varda.utilities import BoundsValidator

            is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
                x, y, source_image.raster.shape, allow_clipping=True
            )

            if not is_valid:
                logger.error(f"Invalid coordinates ({x}, {y}) for source image")
                return False

            # Process wavelength data
            from varda.utilities import WavelengthProcessor

            wavelengths, wavelength_type = WavelengthProcessor.process_wavelength_data(
                source_image.metadata.wavelengths, source_image.raster.shape[2]
            )

            # Get spectrum data
            spectrum = BoundsValidator.safe_pixel_access(
                source_image.raster, safe_x, safe_y
            )

            # Handle invalid values in the spectral data
            from varda.utilities import (
                InvalidDataHandler,
                InvalidValueStrategy,
            )

            clean_wavelengths, clean_spectrum, cleaning_success, cleaning_message = (
                InvalidDataHandler.handle_spectral_pair(
                    wavelengths,
                    spectrum,
                    strategy=InvalidValueStrategy.INTERPOLATE,
                    sync_removal=False,
                )
            )

            if len(clean_spectrum) == 0:
                self.status_changed.emit(
                    self.tool_name, f"No valid spectral data at ({x}, {y})"
                )
                return False

            # Generate spectrum label
            if self._auto_label:
                source_name = (
                    "Primary" if source_index == self._primary_index else "Secondary"
                )
                label = f"{source_name} ({safe_x}, {safe_y})"
            else:
                self._spectrum_counter += 1
                label = f"Spectrum {self._spectrum_counter}"

            # Handle different plot modes
            if self._plot_mode == "replace":
                self._plot_widget.clear_all_spectra()

            # Get color for this spectrum
            color_index = len(self._plot_widget.spectra) % len(
                self._plot_widget.default_colors
            )
            color = self._plot_widget.default_colors[color_index]

            # Add the spectrum using the correct method
            spectrum_id = self._plot_widget.add_spectrum(
                wavelengths=clean_wavelengths,
                values=clean_spectrum,
                label=label,
                color=color,
                coords=(safe_x, safe_y),
                image_index=source_index,
                wavelength_type=wavelength_type,
            )

            if spectrum_id:
                # Manage spectrum count for accumulate mode
                if self._plot_mode == "accumulate":
                    self._manage_spectrum_count()

                # Update status
                click_source = (
                    "Primary" if image_index == self._primary_index else "Secondary"
                )
                data_source = (
                    "Primary" if source_index == self._primary_index else "Secondary"
                )
                status = f"Plotted spectrum from {data_source} image (clicked on {click_source})"
                self.status_changed.emit(self.tool_name, status)

                logger.info(
                    f"Added spectrum: {label} from image {source_index} at ({safe_x}, {safe_y})"
                )
                return True
            else:
                self.status_changed.emit(
                    self.tool_name, f"Failed to extract spectrum at ({x}, {y})"
                )
                return False

        except Exception as e:
            logger.error(f"Error plotting spectrum: {e}")
            self.status_changed.emit(self.tool_name, f"Error: {str(e)}")
            return False

    def _on_images_changed(self, primary_index: int, secondary_index: int):
        """Handle image pair changes"""
        if self._plot_widget:
            # Update plot widget's default image to the source image
            source_index = self._get_source_image_index()
            if source_index is not None:
                self._plot_widget.setImage(source_index)

        logger.debug(
            f"SpectralPlotTool updated for images: {primary_index}, {secondary_index}"
        )

    def _get_source_image_index(self) -> Optional[int]:
        """Get the index of the image to extract spectral data from"""
        if self._spectral_source == "primary":
            return self._primary_index
        elif self._spectral_source == "secondary":
            return self._secondary_index
        return None

    def _manage_spectrum_count(self):
        """Manage spectrum count to stay within maximum limit"""
        if not self._plot_widget:
            return

        spectra_info = self._plot_widget.get_all_spectra_info()
        if len(spectra_info) > self._max_spectra:
            # Remove oldest spectra (assuming they're added in order)
            spectrum_ids = list(spectra_info.keys())
            for spectrum_id in spectrum_ids[: -self._max_spectra]:
                self._plot_widget.remove_spectrum(spectrum_id)

    # Control panel event handlers

    def _on_source_changed(self, source: str):
        """Handle spectral source change"""
        self._spectral_source = source

        # Update plot widget's image reference
        source_index = self._get_source_image_index()
        if source_index is not None and self._plot_widget:
            self._plot_widget.setImage(source_index)

        self.status_changed.emit(
            self.tool_name,
            f"Spectral source: {'Primary' if source == 'primary' else 'Secondary'} image",
        )
        logger.debug(f"Spectral source changed to: {source}")

    def _on_plot_mode_changed(self, mode: str):
        """Handle plot mode change"""
        self._plot_mode = mode
        self.status_changed.emit(self.tool_name, f"Plot mode: {mode}")
        logger.debug(f"Plot mode changed to: {mode}")

    def _on_clear_spectra(self):
        """Handle clear spectra request"""
        if self._plot_widget:
            self._plot_widget.clear_all_spectra()
            self._spectrum_counter = 0
            self.status_changed.emit(self.tool_name, "All spectra cleared")
            logger.debug("Cleared all spectra")

    def _on_auto_label_toggled(self, enabled: bool):
        """Handle auto-label toggle"""
        self._auto_label = enabled
        status = "Auto-labeling enabled" if enabled else "Auto-labeling disabled"
        self.status_changed.emit(self.tool_name, status)

    def _on_max_spectra_changed(self, count: int):
        """Handle max spectra count change"""
        self._max_spectra = count
        self._manage_spectrum_count()  # Apply new limit immediately
        self.status_changed.emit(self.tool_name, f"Max spectra: {count}")

    def get_tool_info(self) -> Dict[str, Any]:
        """Get detailed information about this tool"""
        base_info = super().get_tool_info()
        base_info.update(
            {
                "spectral_source": self._spectral_source,
                "plot_mode": self._plot_mode,
                "auto_label": self._auto_label,
                "max_spectra": self._max_spectra,
                "spectrum_count": (
                    len(self._plot_widget.get_all_spectra_info())
                    if self._plot_widget
                    else 0
                ),
            }
        )
        return base_info
