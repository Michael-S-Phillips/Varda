import logging
import numpy as np
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, QRadioButton, 
    QButtonGroup, QScrollArea, QGridLayout, QSplitter, QTabWidget, QPushButton,
    QLabel, QMessageBox, QMenu, QFrame, QApplication, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QPoint, QDateTime, QSize
from PyQt6.QtGui import QDrag, QPixmap, QPainter, QAction, QIcon

from varda.core.data import ProjectContext
from varda.core.ui.controlpanel import DockableTab
from varda.gui.widgets.image_plot_widget import ImagePlotWidget
from varda.gui.widgets.spectral_properties_panel import SpectralPropertiesPanel, EnhancedImagePlotWidget

logger = logging.getLogger(__name__)


class DraggablePlotThumbnail(QWidget):
    """Draggable thumbnail widget for plot thumbnails."""
    
    thumbnailClicked = pyqtSignal(dict)  # plot_data
    thumbnailRightClicked = pyqtSignal(dict, QPoint)  # plot_data, position
    
    def __init__(self, plot_data: dict, thumbnail_widget: QWidget, parent=None):
        super().__init__(parent)
        self.plot_data = plot_data
        self.thumbnail_widget = thumbnail_widget
        
        # Set up drag and drop
        self.setAcceptDrops(True)
        
        # Create layout and add thumbnail
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(thumbnail_widget)
        
        # Style
        self.setStyleSheet("""
            DraggablePlotThumbnail {
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            DraggablePlotThumbnail:hover {
                border: 2px solid #4CAF50;
                background-color: #F8F8F8;
            }
        """)
    
    def mousePressEvent(self, event):
        """Handle mouse press for drag initiation."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        elif event.button() == Qt.MouseButton.RightButton:
            self.thumbnailRightClicked.emit(self.plot_data, event.globalPosition().toPoint())
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for drag operation."""
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        if not hasattr(self, 'drag_start_position'):
            return
        
        # Check if drag distance is sufficient
        if ((event.position().toPoint() - self.drag_start_position).manhattanLength() < 
            QApplication.startDragDistance()):
            return
        
        # Start drag operation
        drag = QDrag(self)
        mime_data = QMimeData()
        
        # Store plot data as JSON
        import json
        mime_data.setText(json.dumps(self.plot_data))
        mime_data.setData("application/x-varda-plot", json.dumps(self.plot_data).encode())
        
        drag.setMimeData(mime_data)
        
        # Create drag pixmap
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        
        # Execute drag
        drop_action = drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction)
    
    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open plot."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.thumbnailClicked.emit(self.plot_data)
        super().mouseDoubleClickEvent(event)


class PlotWindow(EnhancedImagePlotWidget):
    """Advanced plot window with drag-drop support and properties panel."""
    
    def __init__(self, plot_data: dict, project_context: ProjectContext, parent=None):
        super().__init__(
            proj=project_context,
            imageIndex=plot_data.get('image_index'),
            isWindow=True,
            show_properties_panel=True,
            parent=parent
        )
        
        self.plot_data = plot_data
        self.setWindowTitle(f"Spectral Plot - {plot_data.get('title', 'Unknown')}")
        self.resize(800, 600)
        
        # Override window flags to remove stay-on-top behavior and ensure proper independence
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowCloseButtonHint | 
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowTitleHint
        )
        
        # Ensure window is not transparent
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setWindowOpacity(1.0)

        # Set up drag and drop
        self.setAcceptDrops(True)
        
        # Load initial spectrum
        self._load_initial_spectrum()
    
    def _load_initial_spectrum(self):
        """Load the initial spectrum for this plot."""
        if not self.proj or not self.plot_data:
            return
        
        coords = self.plot_data.get('coords')
        image_index = self.plot_data.get('image_index')
        
        if coords and image_index is not None:
            x, y = coords
            self.showPixelSpectrum(x, y, image_index)
    
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasFormat("application/x-varda-plot"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle drop events to add spectra from other plots."""
        if not event.mimeData().hasFormat("application/x-varda-plot"):
            event.ignore()
            return
        
        try:
            import json
            dropped_plot_data = json.loads(
                event.mimeData().data("application/x-varda-plot").data().decode()
            )
            
            # Add spectrum from dropped plot
            self._add_spectrum_from_plot_data(dropped_plot_data)
            
            event.acceptProposedAction()
            
        except Exception as e:
            logger.error(f"Error handling drop: {e}")
            event.ignore()
    
    def _add_spectrum_from_plot_data(self, plot_data: dict):
        """Add a spectrum from dropped plot data."""
        coords = plot_data.get('coords')
        image_index = plot_data.get('image_index')
        
        if not coords or image_index is None:
            return
        
        try:
            # Get spectral data
            image = self.proj.getImage(image_index)
            x, y = coords
            
            # Get wavelengths
            try:
                wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(float)
            except ValueError:
                wavelengths = np.arange(len(image.metadata.wavelengths), dtype=float)
            
            # Get spectrum
            spectrum = image.raster[y, x, :]
            
            # Add to plot
            spectrum_id = self.add_spectrum(
                wavelengths=wavelengths,
                values=spectrum,
                label=plot_data.get('title', f"Pixel ({x}, {y})"),
                coords=(x, y),
                image_index=image_index
            )
            
            logger.info(f"Added spectrum {spectrum_id} from dropped plot")
            
        except Exception as e:
            logger.error(f"Error adding spectrum from plot data: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Could not add spectrum: {str(e)}"
            )


class PlotManagerTab(DockableTab):
    """Advanced Plot Manager Tab with spectral control integration."""
    
    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Plot Manager", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        
        # Track popup windows
        self.popup_windows = {}  # Dict to track popup windows by plot ID
        self.lastPixelCoords = (0, 0)
        
        # Plot storage and settings
        self.stored_plots = []  # List of stored plot data
        self.plot_counter = 0  # Counter for unique plot IDs
        
        # Settings
        self.context_enabled = False
        self.main_enabled = False
        self.zoom_enabled = True
        self.update_existing = True
        
        # Track the "active" plot for update mode
        self.active_plot_id = None
        
        self._init_ui()
        self._connect_signals()
    
    def _init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Top section - Settings and plot management
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        # Settings Section
        settings_group = QGroupBox("Plot Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # View settings
        view_layout = QHBoxLayout()
        self.context_checkbox = QCheckBox("Context View")
        self.main_checkbox = QCheckBox("Main View") 
        self.zoom_checkbox = QCheckBox("Zoom View")
        
        self.context_checkbox.setChecked(self.context_enabled)
        self.main_checkbox.setChecked(self.main_enabled)
        self.zoom_checkbox.setChecked(self.zoom_enabled)
        
        view_layout.addWidget(self.context_checkbox)
        view_layout.addWidget(self.main_checkbox)
        view_layout.addWidget(self.zoom_checkbox)
        
        # Update behavior settings
        behavior_layout = QVBoxLayout()
        self.update_radio = QRadioButton("Update existing plots")
        self.create_radio = QRadioButton("Create new plots")
        
        self.behavior_group = QButtonGroup()
        self.behavior_group.addButton(self.update_radio)
        self.behavior_group.addButton(self.create_radio)
        
        self.update_radio.setChecked(self.update_existing)
        self.create_radio.setChecked(not self.update_existing)
        
        behavior_layout.addWidget(self.update_radio)
        behavior_layout.addWidget(self.create_radio)
        
        settings_layout.addLayout(view_layout)
        settings_layout.addLayout(behavior_layout)
        
        # Plot type settings
        top_layout.addWidget(settings_group)
        
        # Stored Plots Section with drag-drop support
        plots_group = QGroupBox("Stored Plots (Drag to combine)")
        plots_layout = QVBoxLayout(plots_group)
        
        # Plot controls
        plot_controls = QHBoxLayout()
        self.clear_all_button = QPushButton("Clear All")
        self.clear_all_button.setToolTip("Remove all stored plots")
        self.export_button = QPushButton("Export...")
        self.export_button.setToolTip("Export plot data")
        
        plot_controls.addWidget(self.clear_all_button)
        plot_controls.addWidget(self.export_button)
        plot_controls.addStretch()
        
        plots_layout.addLayout(plot_controls)
        
        # Scroll area for plot thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.plots_widget = QWidget()
        self.plots_layout = QGridLayout(self.plots_widget)
        self.plots_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.plots_widget)
        plots_layout.addWidget(self.scroll_area)
        
        top_layout.addWidget(plots_group)
        
        # Bottom section - Current plot with properties
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        # Current plot section
        current_group = QGroupBox("Current Plot Preview")
        current_layout = QVBoxLayout(current_group)
        
        # Create embedded plot
        self.current_plot = EnhancedImagePlotWidget(
            self.project_context, 
            self.imageIndex, 
            show_properties_panel=False,  # Keep compact for preview
            parent=self
        )
        self.current_plot.setMaximumHeight(200)
        current_layout.addWidget(self.current_plot)
        
        # Quick actions for current plot
        current_actions = QHBoxLayout()
        self.open_advanced_button = QPushButton("Open Advanced")
        self.open_advanced_button.setToolTip("Open current plot in advanced window")
        self.properties_button = QPushButton("Properties")
        self.properties_button.setToolTip("Show properties panel for current plot")
        
        current_actions.addWidget(self.open_advanced_button)
        current_actions.addWidget(self.properties_button)
        current_actions.addStretch()
        
        current_layout.addLayout(current_actions)
        bottom_layout.addWidget(current_group)
        
        # Add to main splitter
        main_splitter.addWidget(top_widget)
        main_splitter.addWidget(bottom_widget)
        main_splitter.setSizes([300, 250])
        
        layout.addWidget(main_splitter)
    
    def _connect_signals(self):
        """Connect all widget signals."""
        # Settings signals
        self.context_checkbox.toggled.connect(self._on_context_toggled)
        self.main_checkbox.toggled.connect(self._on_main_toggled)
        self.zoom_checkbox.toggled.connect(self._on_zoom_toggled)
        self.update_radio.toggled.connect(self._on_behavior_changed)
        
        # Control signals
        self.clear_all_button.clicked.connect(self._clear_all_plots)
        self.export_button.clicked.connect(self._export_plots)
        self.open_advanced_button.clicked.connect(self._open_current_advanced)
        self.properties_button.clicked.connect(self._show_current_properties)
        
        # Current plot signals
        if hasattr(self.current_plot, 'sigClicked'):
            self.current_plot.sigClicked.connect(self.handlePixelPlotClicked)
    
    def _on_context_toggled(self, checked):
        """Handle context view checkbox toggle."""
        self.context_enabled = checked
        
    def _on_main_toggled(self, checked):
        """Handle main view checkbox toggle."""
        self.main_enabled = checked
        
    def _on_zoom_toggled(self, checked):
        """Handle zoom view checkbox toggle."""
        self.zoom_enabled = checked
        
    def _on_behavior_changed(self, checked):
        """Handle update behavior radio button change."""
        old_update_existing = self.update_existing
        
        if checked:  # update_radio was checked
            self.update_existing = True
        else:
            self.update_existing = False
            
        # When switching modes, manage the active plot
        if old_update_existing != self.update_existing:
            if self.update_existing and self.stored_plots:
                # Switching to "update existing" - mark the most recent plot as active
                self.active_plot_id = self.stored_plots[-1]['id']
                logger.debug(f"Switched to update mode. Active plot: {self.active_plot_id}")
            else:
                # Switching to "create new" - clear active plot
                self.active_plot_id = None
                logger.debug("Switched to create new mode. Cleared active plot.")
    
    def should_update_plot(self) -> bool:
        """Check if plot updates should be processed."""
        return self.context_enabled or self.main_enabled or self.zoom_enabled
    
    def showPixelSpectrum(self, x: int, y: int):
        """Update plot with new coordinates and potentially store it."""
        self.lastPixelCoords = (x, y)
        
        # Update current embedded plot
        if hasattr(self.current_plot, "showPixelSpectrum"):
            self.current_plot.showPixelSpectrum(x, y)
        
        # Store plot if enabled for any view
        if self.context_enabled or self.main_enabled or self.zoom_enabled:
            self._store_plot_data(x, y)
    
    def _store_plot_data(self, x: int, y: int):
        """Store plot data and create thumbnail."""
        plot_data = {
            'coords': (x, y),
            'image_index': self.imageIndex,
            'title': f"Pixel ({x}, {y})",
            'timestamp': str(QDateTime.currentDateTime().toString())
        }
        
        if self.update_existing and self.active_plot_id is not None:
            # Update the active plot only
            for i, stored_plot in enumerate(self.stored_plots):
                if stored_plot['id'] == self.active_plot_id:
                    # Update the existing plot data but keep the same ID
                    plot_data['id'] = self.active_plot_id
                    self.stored_plots[i] = plot_data
                    
                    # Refresh thumbnails
                    self._refresh_thumbnails()
                    
                    # Update existing popup if open
                    if self.active_plot_id in self.popup_windows:
                        existing_popup = self.popup_windows[self.active_plot_id]
                        if existing_popup and existing_popup.isVisible():
                            existing_popup.showPixelSpectrum(x, y, self.imageIndex)
                            existing_popup.setWindowTitle(f"Spectral Plot - {plot_data['title']}")
                    
                    logger.debug(f"Updated active plot {self.active_plot_id} with coords ({x}, {y})")
                    return
            
            # If we get here, the active plot wasn't found - create new
            logger.debug(f"Active plot {self.active_plot_id} not found, creating new plot")
            self.active_plot_id = None
        
        # Create new plot entry
        plot_id = f"plot_{self.plot_counter}"
        self.plot_counter += 1
        plot_data['id'] = plot_id
        
        self.stored_plots.append(plot_data)
        self._add_plot_thumbnail(plot_data)
        
        # If we're in update mode, make this the new active plot
        if self.update_existing:
            self.active_plot_id = plot_id
            logger.debug(f"Created new plot {plot_id} and made it active")
        else:
            logger.debug(f"Created new plot {plot_id} in create mode")
    
    def _add_plot_thumbnail(self, plot_data: dict):
        """Add a draggable thumbnail for the stored plot."""
        # Create basic thumbnail widget
        thumb_widget = self._create_basic_thumbnail_widget(plot_data)
        
        # Wrap in draggable container
        draggable_thumb = DraggablePlotThumbnail(plot_data, thumb_widget)
        draggable_thumb.thumbnailClicked.connect(self._open_plot_popup)
        draggable_thumb.thumbnailRightClicked.connect(self._show_thumbnail_context_menu)
        
        # Calculate grid position
        current_count = self.plots_layout.count()
        row = current_count // 3
        col = current_count % 3
        self.plots_layout.addWidget(draggable_thumb, row, col)
        
        logger.debug(f"Added draggable thumbnail for {plot_data['id']} at position ({row}, {col})")
    
    def _create_basic_thumbnail_widget(self, plot_data: dict) -> QWidget:
        """Create basic thumbnail widget."""
        thumb_widget = QWidget()
        thumb_layout = QVBoxLayout(thumb_widget)
        thumb_layout.setSpacing(2)
        
        # Try to generate plot thumbnail
        plot_pixmap = self._generate_plot_thumbnail(plot_data)
        
        if plot_pixmap:
            thumb_button = QPushButton()
            thumb_button.setIcon(QIcon(plot_pixmap))
            thumb_button.setIconSize(QSize(80, 60))
            thumb_button.setFixedSize(80, 60)
            thumb_button.setFlat(True)
            thumb_button.setStyleSheet("QPushButton { border: 1px solid gray; }")
        else:
            thumb_button = QPushButton("📊")
            thumb_button.setFixedSize(80, 60)
        
        thumb_button.setToolTip(f"Click to open {plot_data['title']}")
        
        # Create title label
        title_label = QLabel(plot_data['title'])
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setMaximumWidth(80)
        title_label.setStyleSheet("font-size: 10px;")
        
        thumb_layout.addWidget(thumb_button)
        thumb_layout.addWidget(title_label)
        
        return thumb_widget
    
    def _generate_plot_thumbnail(self, plot_data: dict, size=(80, 60)) -> Optional[QPixmap]:
        """Generate a small thumbnail image of the plot."""
        try:
            # Get the spectral data
            x, y = plot_data['coords']
            image = self.project_context.getImage(plot_data['image_index'])
            
            # Get wavelengths
            try:
                wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(float)
            except ValueError:
                wavelengths = np.arange(len(image.metadata.wavelengths), dtype=float)
            
            # Get spectrum data and handle NaN values
            spectrum = image.raster[y, x, :]
            if np.any(np.isnan(spectrum)):
                spectrum = np.nan_to_num(spectrum, nan=0.0)
            
            if np.all(spectrum == 0) or len(spectrum) == 0:
                spectrum = np.random.random(len(wavelengths)) * 100
            
            # Create thumbnail plot
            import pyqtgraph as pg
            thumb_plot = pg.PlotWidget()
            thumb_plot.setFixedSize(size[0], size[1])
            thumb_plot.hideAxis('left')
            thumb_plot.hideAxis('bottom')
            thumb_plot.setMenuEnabled(False)
            thumb_plot.setMouseEnabled(x=False, y=False)
            thumb_plot.hideButtons()
            thumb_plot.setBackground('white')
            
            # Plot the data
            thumb_plot.plot(wavelengths, spectrum, pen=pg.mkPen(color='blue', width=1))
            
            # Render to pixmap
            thumb_plot.resize(size[0], size[1])
            thumb_plot.updateGeometry()
            
            pixmap = QPixmap(size[0], size[1])
            pixmap.fill()
            
            painter = QPainter(pixmap)
            thumb_plot.render(painter)
            painter.end()
            
            thumb_plot.close()
            thumb_plot.deleteLater()
            
            return pixmap
            
        except Exception as e:
            logger.warning(f"Error generating thumbnail: {e}")
            return None
    
    def _refresh_thumbnails(self):
        """Refresh all thumbnails."""
        logger.debug(f"Refreshing thumbnails for {len(self.stored_plots)} plots")
        
        # Clear existing thumbnails
        for i in reversed(range(self.plots_layout.count())):
            item = self.plots_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
        
        # Re-add all thumbnails
        for i, plot_data in enumerate(self.stored_plots):
            self._add_plot_thumbnail(plot_data)
        
        logger.debug(f"Refreshed {len(self.stored_plots)} thumbnails")
    
    def _open_plot_popup(self, plot_data: dict):
        """Open advanced popup window for the selected plot."""
        plot_id = plot_data['id']
        
        # Check if window already exists
        if plot_id in self.popup_windows:
            existing_popup = self.popup_windows[plot_id]
            if existing_popup and not existing_popup.isVisible():
                del self.popup_windows[plot_id]
            elif existing_popup:
                existing_popup.show()
                existing_popup.raise_()
                existing_popup.activateWindow()
                return
        
        # Always create advanced popup window
        popup = PlotWindow(plot_data, self.project_context, self)
        
        # Set up cleanup
        def cleanup_popup():
            if plot_id in self.popup_windows:
                del self.popup_windows[plot_id]
        
        popup.destroyed.connect(cleanup_popup)
        
        # Store reference and show
        self.popup_windows[plot_id] = popup
        popup.show()
        popup.raise_()
        popup.activateWindow()
    
    def _show_thumbnail_context_menu(self, plot_data: dict, position: QPoint):
        """Show context menu for thumbnail."""
        menu = QMenu(self)
        
        # Open action (always advanced now)
        open_action = QAction("Open Plot", self)
        open_action.triggered.connect(lambda: self._open_plot_popup(plot_data))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        # Management actions
        duplicate_action = QAction("Duplicate", self)
        duplicate_action.triggered.connect(lambda: self._duplicate_plot(plot_data))
        menu.addAction(duplicate_action)
        
        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_plot(plot_data))
        menu.addAction(rename_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self._remove_plot(plot_data))
        menu.addAction(remove_action)
        
        menu.exec(position)
    
    def _duplicate_plot(self, plot_data: dict):
        """Duplicate a plot."""
        new_plot_data = plot_data.copy()
        new_plot_data['id'] = f"plot_{self.plot_counter}"
        new_plot_data['title'] = f"{plot_data['title']} (Copy)"
        self.plot_counter += 1
        
        self.stored_plots.append(new_plot_data)
        self._add_plot_thumbnail(new_plot_data)
    
    def _rename_plot(self, plot_data: dict):
        """Rename a plot."""
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Plot",
            "Enter new name:",
            text=plot_data['title']
        )
        
        if ok and new_name:
            # Update plot data
            for plot in self.stored_plots:
                if plot['id'] == plot_data['id']:
                    plot['title'] = new_name
                    break
            
            # Refresh thumbnails
            self._refresh_thumbnails()
            
            # Update popup window title if open
            if plot_data['id'] in self.popup_windows:
                popup = self.popup_windows[plot_data['id']]
                if popup:
                    popup.setWindowTitle(f"Spectral Plot - {new_name}")
    
    def _remove_plot(self, plot_data: dict):
        """Remove a plot."""
        reply = QMessageBox.question(
            self,
            "Remove Plot",
            f"Remove plot '{plot_data['title']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Close popup if open
            if plot_data['id'] in self.popup_windows:
                popup = self.popup_windows[plot_data['id']]
                if popup:
                    popup.close()
            
            # Remove from stored plots
            self.stored_plots = [p for p in self.stored_plots if p['id'] != plot_data['id']]
            
            # Update active plot if this was it
            if self.active_plot_id == plot_data['id']:
                self.active_plot_id = None
            
            # Refresh thumbnails
            self._refresh_thumbnails()
    
    def _clear_all_plots(self):
        """Clear all stored plots."""
        if not self.stored_plots:
            return
        
        reply = QMessageBox.question(
            self,
            "Clear All Plots",
            f"Remove all {len(self.stored_plots)} plots?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Close all popups
            for popup in list(self.popup_windows.values()):
                if popup:
                    popup.close()
            self.popup_windows.clear()
            
            # Clear data
            self.stored_plots.clear()
            self.active_plot_id = None
            
            # Refresh UI
            self._refresh_thumbnails()
    
    def _export_plots(self):
        """Export plot data."""
        QMessageBox.information(
            self,
            "Export Plots",
            "Plot export functionality will be implemented here.\n"
            "Will support CSV, JSON, and image export formats."
        )
    
    def _open_current_advanced(self):
        """Open current plot in advanced window."""
        if not self.lastPixelCoords:
            QMessageBox.information(self, "No Plot", "No current plot to open.")
            return
        
        # Create temporary plot data
        x, y = self.lastPixelCoords
        temp_plot_data = {
            'id': 'current_temp',
            'coords': (x, y),
            'image_index': self.imageIndex,
            'title': f"Current Pixel ({x}, {y})"
        }
        
        # Open advanced popup
        popup = PlotWindow(temp_plot_data, self.project_context, self)
        popup.show()
    
    def _show_current_properties(self):
        """Show properties panel for current plot."""
        if not hasattr(self.current_plot, 'properties_panel'):
            # Add properties panel to current plot
            properties_panel = SpectralPropertiesPanel(self.current_plot, self)
            
            # Create popup window for properties
            properties_window = QWidget()
            properties_window.setWindowTitle("Current Plot Properties")
            properties_layout = QVBoxLayout(properties_window)
            properties_layout.addWidget(properties_panel)
            properties_window.resize(400, 600)
            properties_window.show()
        
    def handlePixelPlotClicked(self):
        """Handle pixel plot click - delegate to parent control panel."""
        if hasattr(self.parent_control_panel, "handlePixelPlotClicked"):
            self.parent_control_panel.handlePixelPlotClicked()
    
    def setup_view_click_handlers(self, raster_view):
        """Set up click handlers for different views."""
        # This method maintains compatibility with existing code
        pass
    
    def closeEvent(self, event):
        """Clean up all popup windows when the tab is closed."""
        for popup in list(self.popup_windows.values()):
            if popup and popup.isVisible():
                popup.close()
        
        self.popup_windows.clear()
        super().closeEvent(event)