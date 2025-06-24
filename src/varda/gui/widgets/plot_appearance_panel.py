import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QComboBox,
    QLabel, QSpinBox, QFormLayout, QPushButton, QColorDialog, QSlider
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap, QIcon, QPainter
import pyqtgraph as pg

logger = logging.getLogger(__name__)


class ColorButton(QPushButton):
    """Reusable color selection button."""
    
    colorChanged = pyqtSignal(str)
    
    def __init__(self, color: str = "#FFFFFF", size=(40, 25), parent=None):
        super().__init__(parent)
        self.current_color = color
        self.setFixedSize(*size)
        self.clicked.connect(self._select_color)
        self._update_appearance()
    
    def _update_appearance(self):
        """Update button appearance to show current color."""
        pixmap = QPixmap(self.width() - 4, self.height() - 4)
        pixmap.fill(QColor(self.current_color))
        
        painter = QPainter(pixmap)
        painter.setPen(QColor(0, 0, 0))
        painter.drawRect(0, 0, pixmap.width() - 1, pixmap.height() - 1)
        painter.end()
        
        self.setIcon(QIcon(pixmap))
        self.setToolTip(f"Color: {self.current_color}")
    
    def _select_color(self):
        """Open color dialog."""
        color = QColorDialog.getColor(QColor(self.current_color), self, "Select Color")
        if color.isValid():
            self.current_color = color.name()
            self._update_appearance()
            self.colorChanged.emit(self.current_color)
    
    def set_color(self, color: str):
        """Set color programmatically."""
        self.current_color = color
        self._update_appearance()
    
    def get_color(self) -> str:
        """Get current color."""
        return self.current_color


class PlotAppearancePanel(QWidget):
    """Panel for controlling plot-level appearance properties."""
    
    plotPropertyChanged = pyqtSignal(str, object)  # property_name, value
    
    def __init__(self, plot_widget, parent=None):
        super().__init__(parent)
        self.plot_widget = plot_widget
        self._init_ui()
        self._connect_signals()
        self._load_current_settings()
    
    def _init_ui(self):
        """Initialize the appearance controls UI."""
        layout = QVBoxLayout(self)
        
        # Background settings
        bg_group = QGroupBox("Background")
        bg_layout = QFormLayout(bg_group)
        
        # Background color
        bg_color_layout = QHBoxLayout()
        self.bg_color_button = ColorButton("#FFFFFF")
        self.bg_color_button.setToolTip("Plot background color")
        bg_color_layout.addWidget(self.bg_color_button)
        bg_color_layout.addStretch()
        bg_layout.addRow("Color:", bg_color_layout)
        
        layout.addWidget(bg_group)
        
        # Grid settings
        grid_group = QGroupBox("Grid")
        grid_layout = QFormLayout(grid_group)
        
        # Grid visibility
        grid_vis_layout = QHBoxLayout()
        self.grid_x_checkbox = QCheckBox("X Grid")
        self.grid_y_checkbox = QCheckBox("Y Grid")
        self.grid_x_checkbox.setChecked(True)
        self.grid_y_checkbox.setChecked(True)
        grid_vis_layout.addWidget(self.grid_x_checkbox)
        grid_vis_layout.addWidget(self.grid_y_checkbox)
        grid_vis_layout.addStretch()
        grid_layout.addRow("Show:", grid_vis_layout)
        
        # Grid color
        grid_color_layout = QHBoxLayout()
        self.grid_color_button = ColorButton("#CCCCCC")
        self.grid_color_button.setToolTip("Grid line color")
        grid_color_layout.addWidget(self.grid_color_button)
        grid_color_layout.addStretch()
        grid_layout.addRow("Color:", grid_color_layout)
        
        # Grid opacity
        self.grid_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.grid_opacity_slider.setRange(0, 100)
        self.grid_opacity_slider.setValue(50)
        self.grid_opacity_label = QLabel("50%")
        grid_opacity_layout = QHBoxLayout()
        grid_opacity_layout.addWidget(self.grid_opacity_slider)
        grid_opacity_layout.addWidget(self.grid_opacity_label)
        grid_layout.addRow("Opacity:", grid_opacity_layout)
        
        layout.addWidget(grid_group)
        
        # Axes settings
        axes_group = QGroupBox("Axes")
        axes_layout = QFormLayout(axes_group)
        
        # Axis labels
        self.x_label_combo = QComboBox()
        self.x_label_combo.setEditable(True)
        self.x_label_combo.addItems(["Wavelength (nm)", "Band Number", "Frequency (Hz)", "Energy (eV)"])
        self.x_label_combo.setCurrentText("Wavelength (nm)")
        axes_layout.addRow("X Label:", self.x_label_combo)
        
        self.y_label_combo = QComboBox()
        self.y_label_combo.setEditable(True)
        self.y_label_combo.addItems(["Intensity", "Reflectance", "Radiance", "Counts", "Normalized"])
        self.y_label_combo.setCurrentText("Intensity")
        axes_layout.addRow("Y Label:", self.y_label_combo)
        
        # Axis color
        axis_color_layout = QHBoxLayout()
        self.axis_color_button = ColorButton("#000000")
        self.axis_color_button.setToolTip("Axis line and text color")
        axis_color_layout.addWidget(self.axis_color_button)
        axis_color_layout.addStretch()
        axes_layout.addRow("Color:", axis_color_layout)
        
        layout.addWidget(axes_group)
        
        # Title settings
        title_group = QGroupBox("Title")
        title_layout = QFormLayout(title_group)
        
        # Title text
        self.title_combo = QComboBox()
        self.title_combo.setEditable(True)
        self.title_combo.addItems(["Spectral Plot", "Pixel Spectrum", "ROI Spectrum", "Custom"])
        title_layout.addRow("Text:", self.title_combo)
        
        # Title font size
        self.title_size_spin = QSpinBox()
        self.title_size_spin.setRange(8, 24)
        self.title_size_spin.setValue(12)
        self.title_size_spin.setSuffix(" pt")
        title_layout.addRow("Font Size:", self.title_size_spin)
        
        # Title color
        title_color_layout = QHBoxLayout()
        self.title_color_button = ColorButton("#000000")
        self.title_color_button.setToolTip("Title text color")
        title_color_layout.addWidget(self.title_color_button)
        title_color_layout.addStretch()
        title_layout.addRow("Color:", title_color_layout)
        
        layout.addWidget(title_group)
        
        # Legend settings
        legend_group = QGroupBox("Legend")
        legend_layout = QFormLayout(legend_group)
        
        # Legend position
        self.legend_pos_combo = QComboBox()
        self.legend_pos_combo.addItems(["Top Left", "Top Right", "Bottom Left", "Bottom Right"])
        self.legend_pos_combo.setCurrentText("Top Right")
        legend_layout.addRow("Position:", self.legend_pos_combo)
        
        # Legend background
        legend_bg_layout = QHBoxLayout()
        self.legend_bg_button = ColorButton("#FFFFFF")
        self.legend_bg_button.setToolTip("Legend background color")
        legend_bg_layout.addWidget(self.legend_bg_button)
        legend_bg_layout.addStretch()
        legend_layout.addRow("Background:", legend_bg_layout)
        
        # Legend opacity
        self.legend_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.legend_opacity_slider.setRange(0, 100)
        self.legend_opacity_slider.setValue(80)
        self.legend_opacity_label = QLabel("80%")
        legend_opacity_layout = QHBoxLayout()
        legend_opacity_layout.addWidget(self.legend_opacity_slider)
        legend_opacity_layout.addWidget(self.legend_opacity_label)
        legend_layout.addRow("Opacity:", legend_opacity_layout)
        
        layout.addWidget(legend_group)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("Apply All")
        self.apply_button.setToolTip("Apply all appearance changes")
        
        self.reset_button = QPushButton("Reset")
        self.reset_button.setToolTip("Reset to default appearance")
        
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        layout.addStretch()
    
    def _connect_signals(self):
        """Connect all widget signals."""
        # Background
        self.bg_color_button.colorChanged.connect(
            lambda color: self._emit_property_change("background_color", color)
        )
        
        # Grid
        self.grid_x_checkbox.toggled.connect(
            lambda checked: self._emit_property_change("grid_x", checked)
        )
        self.grid_y_checkbox.toggled.connect(
            lambda checked: self._emit_property_change("grid_y", checked)
        )
        self.grid_color_button.colorChanged.connect(
            lambda color: self._emit_property_change("grid_color", color)
        )
        self.grid_opacity_slider.valueChanged.connect(self._on_grid_opacity_changed)
        
        # Axes
        self.x_label_combo.currentTextChanged.connect(
            lambda text: self._emit_property_change("x_label", text)
        )
        self.y_label_combo.currentTextChanged.connect(
            lambda text: self._emit_property_change("y_label", text)
        )
        self.axis_color_button.colorChanged.connect(
            lambda color: self._emit_property_change("axis_color", color)
        )
        
        # Title
        self.title_combo.currentTextChanged.connect(
            lambda text: self._emit_property_change("title_text", text)
        )
        self.title_size_spin.valueChanged.connect(
            lambda size: self._emit_property_change("title_size", size)
        )
        self.title_color_button.colorChanged.connect(
            lambda color: self._emit_property_change("title_color", color)
        )
        
        # Legend
        self.legend_pos_combo.currentTextChanged.connect(
            lambda pos: self._emit_property_change("legend_position", pos)
        )
        self.legend_bg_button.colorChanged.connect(
            lambda color: self._emit_property_change("legend_background", color)
        )
        self.legend_opacity_slider.valueChanged.connect(self._on_legend_opacity_changed)
        
        # Buttons
        self.apply_button.clicked.connect(self._apply_all_changes)
        self.reset_button.clicked.connect(self._reset_to_defaults)
    
    def _on_grid_opacity_changed(self, value):
        """Handle grid opacity slider change."""
        self.grid_opacity_label.setText(f"{value}%")
        self._emit_property_change("grid_opacity", value / 100.0)
    
    def _on_legend_opacity_changed(self, value):
        """Handle legend opacity slider change."""
        self.legend_opacity_label.setText(f"{value}%")
        self._emit_property_change("legend_opacity", value / 100.0)
    
    def _emit_property_change(self, property_name: str, value):
        """Emit property change signal and apply immediately."""
        self.plotPropertyChanged.emit(property_name, value)
        self._apply_property_to_plot(property_name, value)
    
    def _apply_property_to_plot(self, property_name: str, value):
        """Apply a single property change to the plot widget."""
        if not self.plot_widget or not hasattr(self.plot_widget, 'plot_widget'):
            return
        
        plot_item = self.plot_widget.plot_widget.getPlotItem()
        
        try:
            if property_name == "background_color":
                self.plot_widget.plot_widget.setBackground(value)
            
            elif property_name == "grid_x":
                self.plot_widget.plot_widget.showGrid(x=value, y=self.grid_y_checkbox.isChecked())
            
            elif property_name == "grid_y":
                self.plot_widget.plot_widget.showGrid(x=self.grid_x_checkbox.isChecked(), y=value)
            
            elif property_name == "grid_color":
                # PyQtGraph doesn't directly support grid color change, but we can set it
                pass
            
            elif property_name == "grid_opacity":
                # Set grid alpha if possible
                pass
            
            elif property_name == "x_label":
                plot_item.setLabel('bottom', value)
            
            elif property_name == "y_label":
                plot_item.setLabel('left', value)
            
            elif property_name == "axis_color":
                # Set axis color (PyQtGraph has limited support)
                pass
            
            elif property_name == "title_text":
                plot_item.setTitle(value)
            
            elif property_name == "title_size":
                # Set title font size
                pass
            
            elif property_name == "title_color":
                # Set title color
                pass
            
            elif property_name == "legend_position":
                # Move legend to new position
                legend = plot_item.legend
                if legend:
                    # Remove and re-add legend in new position
                    pass
            
            elif property_name == "legend_background":
                # Set legend background color
                legend = plot_item.legend
                if legend:
                    legend.setBrush(pg.mkBrush(value))
            
            elif property_name == "legend_opacity":
                # Set legend opacity
                pass
        
        except Exception as e:
            logger.warning(f"Could not apply property {property_name}: {e}")
    
    def _apply_all_changes(self):
        """Apply all current settings to the plot."""
        properties = {
            "background_color": self.bg_color_button.get_color(),
            "grid_x": self.grid_x_checkbox.isChecked(),
            "grid_y": self.grid_y_checkbox.isChecked(),
            "grid_color": self.grid_color_button.get_color(),
            "grid_opacity": self.grid_opacity_slider.value() / 100.0,
            "x_label": self.x_label_combo.currentText(),
            "y_label": self.y_label_combo.currentText(),
            "axis_color": self.axis_color_button.get_color(),
            "title_text": self.title_combo.currentText(),
            "title_size": self.title_size_spin.value(),
            "title_color": self.title_color_button.get_color(),
            "legend_position": self.legend_pos_combo.currentText(),
            "legend_background": self.legend_bg_button.get_color(),
            "legend_opacity": self.legend_opacity_slider.value() / 100.0,
        }
        
        for prop_name, value in properties.items():
            self._apply_property_to_plot(prop_name, value)
    
    def _reset_to_defaults(self):
        """Reset all settings to defaults."""
        self.bg_color_button.set_color("#FFFFFF")
        self.grid_x_checkbox.setChecked(True)
        self.grid_y_checkbox.setChecked(True)
        self.grid_color_button.set_color("#CCCCCC")
        self.grid_opacity_slider.setValue(50)
        self.x_label_combo.setCurrentText("Wavelength (nm)")
        self.y_label_combo.setCurrentText("Intensity")
        self.axis_color_button.set_color("#000000")
        self.title_combo.setCurrentText("Spectral Plot")
        self.title_size_spin.setValue(12)
        self.title_color_button.set_color("#000000")
        self.legend_pos_combo.setCurrentText("Top Right")
        self.legend_bg_button.set_color("#FFFFFF")
        self.legend_opacity_slider.setValue(80)
        
        self._apply_all_changes()
    
    # TODO: Implement loading current settings from the plot widget
    def _load_current_settings(self):
        """Load current plot settings into the controls."""
        if not self.plot_widget:
            return
        
        # Try to read current settings from plot widget
        # This would be enhanced to read actual current values
        pass
    
    def get_all_properties(self) -> Dict[str, Any]:
        """Get all current property values."""
        return {
            "background_color": self.bg_color_button.get_color(),
            "grid_x": self.grid_x_checkbox.isChecked(),
            "grid_y": self.grid_y_checkbox.isChecked(),
            "grid_color": self.grid_color_button.get_color(),
            "grid_opacity": self.grid_opacity_slider.value() / 100.0,
            "x_label": self.x_label_combo.currentText(),
            "y_label": self.y_label_combo.currentText(),
            "axis_color": self.axis_color_button.get_color(),
            "title_text": self.title_combo.currentText(),
            "title_size": self.title_size_spin.value(),
            "title_color": self.title_color_button.get_color(),
            "legend_position": self.legend_pos_combo.currentText(),
            "legend_background": self.legend_bg_button.get_color(),
            "legend_opacity": self.legend_opacity_slider.value() / 100.0,
        }
    
    def set_properties(self, properties: Dict[str, Any]):
        """Set multiple properties at once."""
        for prop_name, value in properties.items():
            if prop_name == "background_color":
                self.bg_color_button.set_color(value)
            elif prop_name == "grid_x":
                self.grid_x_checkbox.setChecked(value)
            elif prop_name == "grid_y":
                self.grid_y_checkbox.setChecked(value)
            elif prop_name == "grid_color":
                self.grid_color_button.set_color(value)
            elif prop_name == "grid_opacity":
                self.grid_opacity_slider.setValue(int(value * 100))
            elif prop_name == "x_label":
                self.x_label_combo.setCurrentText(value)
            elif prop_name == "y_label":
                self.y_label_combo.setCurrentText(value)
            elif prop_name == "axis_color":
                self.axis_color_button.set_color(value)
            elif prop_name == "title_text":
                self.title_combo.setCurrentText(value)
            elif prop_name == "title_size":
                self.title_size_spin.setValue(value)
            elif prop_name == "title_color":
                self.title_color_button.set_color(value)
            elif prop_name == "legend_position":
                self.legend_pos_combo.setCurrentText(value)
            elif prop_name == "legend_background":
                self.legend_bg_button.set_color(value)
            elif prop_name == "legend_opacity":
                self.legend_opacity_slider.setValue(int(value * 100))