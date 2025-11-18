import logging
from typing import Dict, Optional, Any
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QColorDialog,
    QSplitter,
    QFormLayout,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter

from varda.common._old_widgets.image_plot_widget import ImagePlotWidget

logger = logging.getLogger(__name__)


class ColorButton(QPushButton):
    """Custom button widget for color selection."""

    colorChanged = pyqtSignal(str)  # Emits color as hex string

    def __init__(self, color: str = "#0000FF", parent=None):
        super().__init__(parent)
        self.current_color = color
        self.setFixedSize(30, 25)
        self.clicked.connect(self._select_color)
        self._update_appearance()

    def _update_appearance(self):
        """Update button appearance to show current color."""
        # Create a colored pixmap
        pixmap = QPixmap(24, 19)
        pixmap.fill(QColor(self.current_color))

        # Add border
        painter = QPainter(pixmap)
        painter.setPen(QColor(0, 0, 0))
        painter.drawRect(0, 0, 23, 18)
        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setToolTip(f"Color: {self.current_color}")

    def _select_color(self):
        """Open color dialog for color selection."""
        color = QColorDialog.getColor(
            QColor(self.current_color), self, "Select Spectrum Color"
        )

        if color.isValid():
            self.current_color = color.name()
            self._update_appearance()
            self.colorChanged.emit(self.current_color)

    def set_color(self, color: str):
        """Set the color programmatically."""
        self.current_color = color
        self._update_appearance()

    def get_color(self) -> str:
        """Get the current color as hex string."""
        return self.current_color


class SpectrumListWidget(QListWidget):
    """Custom list widget for displaying spectra with color indicators."""

    spectrumSelectionChanged = pyqtSignal(str)  # spectrum_id
    spectrumVisibilityToggled = pyqtSignal(str, bool)  # spectrum_id, visible

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)

    def add_spectrum_item(self, spectrum_id: str, spectrum_info: Dict[str, Any]):
        """Add a spectrum to the list."""
        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, spectrum_id)

        # Create display text with color indicator
        label = spectrum_info.get("label", spectrum_id)
        visible = spectrum_info.get("visible", True)

        item.setText(f"{label}")
        item.setToolTip(
            f"ID: {spectrum_id}\nCoords: {spectrum_info.get('coords', 'N/A')}"
        )

        # Set checkable for visibility toggle
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
        )

        self.addItem(item)
        return item

    def update_spectrum_item(self, spectrum_id: str, spectrum_info: Dict[str, Any]):
        """Update an existing spectrum item."""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == spectrum_id:
                label = spectrum_info.get("label", spectrum_id)
                visible = spectrum_info.get("visible", True)

                item.setText(f"{label}")
                item.setCheckState(
                    Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked
                )
                break

    def remove_spectrum_item(self, spectrum_id: str):
        """Remove a spectrum from the list."""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == spectrum_id:
                self.takeItem(i)
                break

    def get_selected_spectrum_id(self) -> Optional[str]:
        """Get the currently selected spectrum ID."""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None

    def _on_selection_changed(self):
        """Handle selection changes."""
        spectrum_id = self.get_selected_spectrum_id()
        if spectrum_id:
            self.spectrumSelectionChanged.emit(spectrum_id)

    def _on_item_double_clicked(self, item):
        """Handle double-click to toggle visibility."""
        spectrum_id = item.data(Qt.ItemDataRole.UserRole)
        current_state = item.checkState()
        new_state = (
            Qt.CheckState.Unchecked
            if current_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        item.setCheckState(new_state)

        visible = new_state == Qt.CheckState.Checked
        self.spectrumVisibilityToggled.emit(spectrum_id, visible)


class SpectrumPropertiesWidget(QWidget):
    """Widget for editing properties of a selected spectrum."""

    propertyChanged = pyqtSignal(str, str, object)  # spectrum_id, property_name, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_spectrum_id = None
        self.current_spectrum_info = None
        self._init_ui()
        self._connect_signals()
        self.setEnabled(False)  # Disabled until spectrum is selected

    def _init_ui(self):
        """Initialize the properties UI."""
        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel("Spectrum Properties")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(self.title_label)

        # Properties form
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)

        # Label
        self.label_edit = QComboBox()
        self.label_edit.setEditable(True)
        self.label_edit.setToolTip("Display label for the spectrum")
        form_layout.addRow("Label:", self.label_edit)

        # Color
        color_layout = QHBoxLayout()
        self.color_button = ColorButton("#0000FF")
        self.color_button.setToolTip("Line color")
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        form_layout.addRow("Color:", color_layout)

        # Line width
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(1, 10)
        self.line_width_spin.setValue(1)
        self.line_width_spin.setToolTip("Line thickness in pixels")
        form_layout.addRow("Line Width:", self.line_width_spin)

        # Marker symbol
        self.marker_combo = QComboBox()
        self.marker_combo.addItems(
            [
                "None",
                "Circle (o)",
                "Square (s)",
                "Triangle (t)",
                "Diamond (d)",
                "Plus (+)",
                "Cross (x)",
                "Star (*)",
            ]
        )
        self.marker_combo.setToolTip("Marker symbol for data points")
        form_layout.addRow("Marker:", self.marker_combo)

        # Marker size
        self.marker_size_spin = QSpinBox()
        self.marker_size_spin.setRange(1, 20)
        self.marker_size_spin.setValue(5)
        self.marker_size_spin.setToolTip("Marker size in pixels")
        form_layout.addRow("Marker Size:", self.marker_size_spin)

        # Visibility
        self.visible_checkbox = QCheckBox("Visible")
        self.visible_checkbox.setChecked(True)
        self.visible_checkbox.setToolTip("Show/hide this spectrum")
        form_layout.addRow("", self.visible_checkbox)

        layout.addWidget(form_widget)
        layout.addStretch()

        # Action buttons
        button_layout = QHBoxLayout()

        self.apply_button = QPushButton("Apply")
        self.apply_button.setToolTip("Apply changes to spectrum")
        self.apply_button.clicked.connect(self._apply_changes)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setToolTip("Remove this spectrum from plot")
        self.remove_button.setStyleSheet("color: red;")
        self.remove_button.clicked.connect(self._remove_spectrum)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.remove_button)
        layout.addLayout(button_layout)

    def _connect_signals(self):
        """Connect widget signals."""
        self.color_button.colorChanged.connect(self._on_property_changed)
        self.line_width_spin.valueChanged.connect(self._on_property_changed)
        self.marker_combo.currentTextChanged.connect(self._on_property_changed)
        self.marker_size_spin.valueChanged.connect(self._on_property_changed)
        self.visible_checkbox.toggled.connect(self._on_property_changed)
        self.label_edit.currentTextChanged.connect(self._on_property_changed)

    def set_spectrum(
        self, spectrum_id: Optional[str], spectrum_info: Optional[Dict[str, Any]]
    ):
        """Set the spectrum to edit."""
        self.current_spectrum_id = spectrum_id
        self.current_spectrum_info = spectrum_info

        if spectrum_id and spectrum_info:
            self.setEnabled(True)
            self.title_label.setText(
                f"Properties: {spectrum_info.get('label', spectrum_id)}"
            )

            # Update controls with spectrum data
            self._update_controls(spectrum_info)
        else:
            self.setEnabled(False)
            self.title_label.setText("Spectrum Properties")

    def _update_controls(self, spectrum_info: Dict[str, Any]):
        """Update control values from spectrum info."""
        # Block signals during update
        self.blockSignals(True)

        # Label
        label = spectrum_info.get("label", "")
        self.label_edit.setCurrentText(label)

        # Color
        color = spectrum_info.get("color", "#0000FF")
        self.color_button.set_color(color)

        # Line width
        line_width = spectrum_info.get("line_width", 1)
        self.line_width_spin.setValue(line_width)

        # Marker
        marker_symbol = spectrum_info.get("marker_symbol", None)
        marker_map = {
            None: "None",
            "o": "Circle (o)",
            "s": "Square (s)",
            "t": "Triangle (t)",
            "d": "Diamond (d)",
            "+": "Plus (+)",
            "x": "Cross (x)",
            "*": "Star (*)",
        }
        marker_text = marker_map.get(marker_symbol, "None")
        self.marker_combo.setCurrentText(marker_text)

        # Marker size
        marker_size = spectrum_info.get("marker_size", 5)
        self.marker_size_spin.setValue(marker_size)

        # Visibility
        visible = spectrum_info.get("visible", True)
        self.visible_checkbox.setChecked(visible)

        self.blockSignals(False)

    def _on_property_changed(self):
        """Handle property changes."""
        # Auto-apply changes if spectrum is selected
        if self.current_spectrum_id:
            self._apply_changes()

    def _apply_changes(self):
        """Apply current property values to the spectrum."""
        if not self.current_spectrum_id:
            return

        # Get marker symbol
        marker_text = self.marker_combo.currentText()
        marker_map = {
            "None": None,
            "Circle (o)": "o",
            "Square (s)": "s",
            "Triangle (t)": "t",
            "Diamond (d)": "d",
            "Plus (+)": "+",
            "Cross (x)": "x",
            "Star (*)": "*",
        }
        marker_symbol = marker_map.get(marker_text, None)

        # Emit property changes
        properties = {
            "label": self.label_edit.currentText(),
            "color": self.color_button.get_color(),
            "line_width": self.line_width_spin.value(),
            "marker_symbol": marker_symbol,
            "marker_size": self.marker_size_spin.value(),
            "visible": self.visible_checkbox.isChecked(),
        }

        for prop_name, value in properties.items():
            self.propertyChanged.emit(self.current_spectrum_id, prop_name, value)

    def _remove_spectrum(self):
        """Remove the current spectrum."""
        if not self.current_spectrum_id:
            return

        reply = QMessageBox.question(
            self,
            "Remove Spectrum",
            f"Remove spectrum '{self.current_spectrum_info.get('label', self.current_spectrum_id)}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.propertyChanged.emit(self.current_spectrum_id, "remove", True)


class SpectralPropertiesPanel(QWidget):
    """Main panel for managing spectral line properties."""

    def __init__(self, plot_widget: ImagePlotWidget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self._init_ui()
        self._connect_signals()
        self._refresh_spectrum_list()

    def _init_ui(self):
        """Initialize the panel UI with absolutely minimal splitter intervention."""
        layout = QVBoxLayout(self)

        # Create splitter with default settings - no custom configuration
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Spectrum list
        list_frame = QGroupBox("Spectra")
        list_layout = QVBoxLayout(list_frame)

        self.spectrum_list = SpectrumListWidget()
        list_layout.addWidget(self.spectrum_list)

        # List controls
        list_controls = QHBoxLayout()
        self.add_button = QPushButton("Add...")
        self.clear_button = QPushButton("Clear All")
        list_controls.addWidget(self.add_button)
        list_controls.addWidget(self.clear_button)
        list_controls.addStretch()
        list_layout.addLayout(list_controls)

        # Right side - Properties
        props_frame = QGroupBox("Properties")
        props_layout = QVBoxLayout(props_frame)
        self.properties_widget = SpectrumPropertiesWidget()
        props_layout.addWidget(self.properties_widget)

        # Add to splitter - no size constraints
        splitter.addWidget(list_frame)
        splitter.addWidget(props_frame)

        # NO splitter signal connections at all

        layout.addWidget(splitter)

        # Legend controls
        legend_frame = QGroupBox("Legend")
        legend_layout = QHBoxLayout(legend_frame)
        self.legend_checkbox = QCheckBox("Show Legend")
        self.legend_checkbox.setChecked(True)
        legend_layout.addWidget(self.legend_checkbox)
        legend_layout.addStretch()
        layout.addWidget(legend_frame)

    def _connect_signals(self):
        """Connect widget signals."""
        # Plot widget signals
        self.plot_widget.sigSpectrumAdded.connect(self._on_spectrum_added)
        self.plot_widget.sigSpectrumRemoved.connect(self._on_spectrum_removed)
        self.plot_widget.sigSpectrumUpdated.connect(self._on_spectrum_updated)

        # List signals
        self.spectrum_list.spectrumSelectionChanged.connect(self._on_spectrum_selected)
        self.spectrum_list.spectrumVisibilityToggled.connect(
            self._on_visibility_toggled
        )

        # Properties signals
        self.properties_widget.propertyChanged.connect(self._on_property_changed)

        # Control signals
        self.add_button.clicked.connect(self._add_spectrum)
        self.clear_button.clicked.connect(self._clear_all_spectra)
        self.legend_checkbox.toggled.connect(self._on_legend_toggled)

    def _refresh_spectrum_list(self):
        """Refresh the spectrum list from the plot widget."""
        self.spectrum_list.clear()

        spectra_info = self.plot_widget.get_all_spectra_info()
        for spectrum_id, info in spectra_info.items():
            self.spectrum_list.add_spectrum_item(spectrum_id, info)

    def _on_spectrum_added(self, spectrum_id: str):
        """Handle spectrum added to plot."""
        spectrum_info = self.plot_widget.get_spectrum_info(spectrum_id)
        if spectrum_info:
            self.spectrum_list.add_spectrum_item(spectrum_id, spectrum_info)

    def _on_spectrum_removed(self, spectrum_id: str):
        """Handle spectrum removed from plot."""
        self.spectrum_list.remove_spectrum_item(spectrum_id)

        # Clear properties if this was the selected spectrum
        if self.properties_widget.current_spectrum_id == spectrum_id:
            self.properties_widget.set_spectrum(None, None)

    def _on_spectrum_updated(self, spectrum_id: str):
        """Handle spectrum updated in plot."""
        spectrum_info = self.plot_widget.get_spectrum_info(spectrum_id)
        if spectrum_info:
            self.spectrum_list.update_spectrum_item(spectrum_id, spectrum_info)

            # Update properties if this is the selected spectrum
            if self.properties_widget.current_spectrum_id == spectrum_id:
                self.properties_widget.set_spectrum(spectrum_id, spectrum_info)

    def _on_spectrum_selected(self, spectrum_id: str):
        """Handle spectrum selection in list."""
        spectrum_info = self.plot_widget.get_spectrum_info(spectrum_id)
        self.properties_widget.set_spectrum(spectrum_id, spectrum_info)

    def _on_visibility_toggled(self, spectrum_id: str, visible: bool):
        """Handle visibility toggle from list."""
        self.plot_widget.set_spectrum_visibility(spectrum_id, visible)

    def _on_property_changed(self, spectrum_id: str, property_name: str, value):
        """Handle property changes from properties widget."""
        if property_name == "remove":
            self.plot_widget.remove_spectrum(spectrum_id)
        else:
            # Update spectrum properties
            self.plot_widget.update_spectrum_properties(
                spectrum_id, **{property_name: value}
            )

    def _add_spectrum(self):
        """Add a new spectrum (placeholder - could open file dialog, etc.)."""
        QMessageBox.information(
            self,
            "Add Spectrum",
            "This feature will be implemented to add spectra from files, ROIs, etc.",
        )

    def _clear_all_spectra(self):
        """Clear all spectra from the plot."""
        if not self.plot_widget.get_spectrum_ids():
            return

        reply = QMessageBox.question(
            self,
            "Clear All Spectra",
            "Remove all spectra from the plot?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.plot_widget.clear_all_spectra()

    def _on_legend_toggled(self, checked: bool):
        """Handle legend visibility toggle."""
        self.plot_widget.set_legend_visible(checked)


# Integration class for adding properties panel to plot windows
class EnhancedImagePlotWidget(ImagePlotWidget):
    """Enhanced ImagePlotWidget with integrated properties panel."""

    def __init__(self, *args, show_properties_panel: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_properties_panel = show_properties_panel

        if show_properties_panel:
            self._add_properties_panel()

    def _add_properties_panel(self):
        """Add properties panel to the widget with improved splitter handling."""
        # Get the existing layout - ImagePlotWidget already created one
        existing_layout = self.layout()
        if not existing_layout:
            logger.error("No existing layout found in ImagePlotWidget")
            return

        # Remove the plot_widget from the existing layout
        existing_layout.removeWidget(self.plot_widget)
        self.plot_widget.setParent(
            None
        )  # Explicitly unparent before adding to splitter

        # Clear the layout to ensure only the splitter is present
        while existing_layout.count():
            item = existing_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

        # Create horizontal splitter with proper configuration
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)  # Prevent complete collapse
        splitter.setMinimumSize(400, 300)  # Set a minimum size for the splitter

        # Configure splitter behavior
        splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        splitter.setContentsMargins(0, 0, 0, 0)

        # Ensure plot widget has proper size policy
        self.plot_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Add plot widget to splitter
        splitter.addWidget(self.plot_widget)

        # Create properties panel with proper configuration
        self.properties_panel = SpectralPropertiesPanel(self)
        self.properties_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )

        # Add properties panel to splitter
        splitter.addWidget(self.properties_panel)

        # Configure stretch factors (plot area gets priority)
        splitter.setStretchFactor(0, 3)  # Plot widget gets 3x stretch
        splitter.setStretchFactor(1, 1)  # Properties panel gets 1x stretch

        # Add splitter to the existing layout
        existing_layout.addWidget(splitter)
        splitter.show()  # Force splitter to be shown

        # Store splitter reference for later access
        self._main_splitter = splitter

        # Set initial splitter sizes after widget is shown, to avoid zero-size issues
        def set_splitter_sizes():
            total_width = self.width() if self.width() > 0 else 900
            plot_width = int(total_width * 0.7)
            props_width = int(total_width * 0.3)
            self._main_splitter.setSizes([plot_width, props_width])

        QTimer.singleShot(0, set_splitter_sizes)

        # Comment out forced layout updates
        # self.updateGeometry()
        # self.update()
