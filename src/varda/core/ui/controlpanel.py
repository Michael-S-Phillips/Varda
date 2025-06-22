import logging
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QTreeWidget,
    QTreeWidgetItem,
    QDockWidget,
    QLabel,
    QWidget,
    QScrollArea,
    QPushButton,
    QTabWidget,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
import numpy as np

from varda.core.data import ProjectContext
from varda.features.image_view_roi import getROIView
from varda.features.image_view_band import BandManager
from varda.features.image_view_stretch import StretchManager
from varda.features.image_view_metadata import openMetadataEditor
from varda.gui.widgets.image_plot_widget import ImagePlotWidget

logger = logging.getLogger(__name__)


class DockableTab(QWidget):
    """Base class for tabs that can be docked as separate modules."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.parent_control_panel = parent
        self.docked_widget = None

    def pop_out(self):
        """Pop this tab out as a separate dockable widget."""
        if self.docked_widget is not None:
            return  # Already popped out

        # Create a new dock widget
        self.docked_widget = QDockWidget(self.title, self.parent_control_panel)
        self.docked_widget.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        # Remove from tab widget and add to dock
        if self.parent():
            self.setParent(None)
        self.docked_widget.setWidget(self)

        # Add to main window
        main_window = self.parent_control_panel.parent()
        if main_window:
            main_window.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.docked_widget
            )

        # Connect close event to return to tab
        self.docked_widget.visibilityChanged.connect(self._on_dock_visibility_changed)

    def _on_dock_visibility_changed(self, visible):
        """Handle when the docked widget is closed."""
        if not visible and self.docked_widget:
            self.dock_in()

    def dock_in(self):
        """Return this tab to the control panel."""
        if self.docked_widget is None:
            return

        # Remove from dock widget
        self.docked_widget.setWidget(None)
        self.docked_widget.close()
        self.docked_widget = None

        # Add back to tab widget
        if self.parent_control_panel and hasattr(
            self.parent_control_panel, "tabWidget"
        ):
            self.parent_control_panel.tabWidget.addTab(self, self.title)


class MetadataTab(DockableTab):
    """Tab for metadata editing functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Metadata", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.editMetadataButton = QPushButton("Edit Metadata")
        self.editMetadataButton.setToolTip("View and edit image metadata properties")
        self.editMetadataButton.clicked.connect(
            lambda: openMetadataEditor(self.project_context, self.imageIndex, self)
        )

        layout.addWidget(self.editMetadataButton)
        layout.addStretch()


class ROITab(DockableTab):
    """Tab for ROI management functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, rasterView, parent=None):
        super().__init__("ROI", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self.rasterView = rasterView
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.ROITable = getROIView(self.project_context, self.imageIndex, self)
        self.ROITable.viewModel.setRasterView(self.rasterView)

        # Connect signals for ROI selection
        self.ROITable.roiSelectionChanged.connect(
            lambda roi_index: (
                self.rasterView.highlightROI(roi_index)
                if hasattr(self.rasterView, "highlightROI")
                else None
            )
        )

        layout.addWidget(self.ROITable)


class BandTab(DockableTab):
    """Tab for band selection functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Band Selection", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.bandView = BandManager(self.project_context, self.imageIndex, self)
        layout.addWidget(self.bandView)


class StretchTab(DockableTab):
    """Tab for stretch options functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, rasterView, parent=None):
        super().__init__("Stretch Options", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self.rasterView = rasterView
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.histogramView = StretchManager(self.project_context, self.imageIndex, self)
        self.histogramView.sigStretchSelected.connect(self.rasterView.selectStretch)

        layout.addWidget(self.histogramView)


class PlotManagerTab(DockableTab):
    """Tab for plot management and settings functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Plot Manager", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        
        # Track multiple popup windows instead of just one
        self.popup_windows = {}  # Dict to track popup windows by plot ID
        self.lastPixelCoords = (0, 0)
        
        # Plot storage and settings
        self.stored_plots = []  # List of stored plot data
        self.plot_counter = 0  # Counter for unique plot IDs
        
        # Settings
        self.context_enabled = False
        self.main_enabled = False
        self.zoom_enabled = False
        self.update_existing = True  # True: update existing, False: create new
        
        self._init_ui()

    def _init_ui(self):
        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QGroupBox, QCheckBox, 
            QRadioButton, QButtonGroup, QScrollArea, QGridLayout
        )
        
        layout = QVBoxLayout(self)
        
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
        
        self.context_checkbox.toggled.connect(self._on_context_toggled)
        self.main_checkbox.toggled.connect(self._on_main_toggled)
        self.zoom_checkbox.toggled.connect(self._on_zoom_toggled)
        
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
        
        self.update_radio.toggled.connect(self._on_behavior_changed)
        
        behavior_layout.addWidget(self.update_radio)
        behavior_layout.addWidget(self.create_radio)
        
        settings_layout.addLayout(view_layout)
        settings_layout.addLayout(behavior_layout)
        
        # Stored Plots Section
        plots_group = QGroupBox("Stored Plots")
        plots_layout = QVBoxLayout(plots_group)
        
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
        
        # Add sections to main layout
        layout.addWidget(settings_group)
        layout.addWidget(plots_group)
        
        # Initialize with current pixel plot if available
        self._create_initial_plot()

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
        if checked:  # update_radio was checked
            self.update_existing = True
        else:
            self.update_existing = False

    def _create_initial_plot(self):
        """Create initial embedded plot widget for immediate viewing."""
        self.current_plot = ImagePlotWidget(
            self.project_context, self.imageIndex, parent=self
        )
        self.current_plot.sigClicked.connect(self.handlePixelPlotClicked)
        self.current_plot.setMaximumHeight(150)  # Keep it compact
        
        # Add to layout at the bottom
        if hasattr(self, 'layout'):
            self.layout().addWidget(self.current_plot)

    def handlePixelPlotClicked(self):
        """Handle pixel plot click - delegate to parent control panel."""
        if hasattr(self.parent_control_panel, "handlePixelPlotClicked"):
            self.parent_control_panel.handlePixelPlotClicked()

    def showPixelSpectrum(self, x, y):
        """Update plot with new coordinates and potentially store it."""
        self.lastPixelCoords = (x, y)
        
        # Update current embedded plot
        if hasattr(self.current_plot, "showPixelSpectrum"):
            self.current_plot.showPixelSpectrum(x, y)
        
        # Store plot if enabled for any view
        if self.context_enabled or self.main_enabled or self.zoom_enabled:
            self._store_plot_data(x, y)

    def _store_plot_data(self, x, y):
        """Store plot data and create thumbnail."""
        import copy
        from PyQt6.QtWidgets import QLabel, QPushButton
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QSize
        
        # Create plot data entry
        plot_id = f"plot_{self.plot_counter}"
        self.plot_counter += 1
        
        plot_data = {
            'id': plot_id,
            'coords': (x, y),
            'image_index': self.imageIndex,
            'title': f"Pixel ({x}, {y})"
        }
        
        if self.update_existing and self.stored_plots:
            # Update the most recent plot but preserve the original ID
            old_plot_data = self.stored_plots[-1]
            plot_data['id'] = old_plot_data['id']  # Keep the same ID for consistency
            self.stored_plots[-1] = plot_data
            self._refresh_thumbnails()
            
            # If there's an existing popup for this plot, update it
            if plot_data['id'] in self.popup_windows:
                existing_popup = self.popup_windows[plot_data['id']]
                if existing_popup and existing_popup.isVisible():
                    existing_popup.showPixelSpectrum(x, y, self.imageIndex)
                    existing_popup.setWindowTitle(f"Plot Manager - {plot_data['title']}")
        else:
            # Create new plot entry
            self.stored_plots.append(plot_data)
            self._add_plot_thumbnail(plot_data)

    def _add_plot_thumbnail(self, plot_data):
        """Add a thumbnail for the stored plot."""
        from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout
        from PyQt6.QtCore import QSize
        
        # Create thumbnail container
        thumb_widget = QWidget()
        thumb_layout = QVBoxLayout(thumb_widget)
        thumb_layout.setSpacing(2)
        
        # Create thumbnail button (placeholder for now)
        thumb_button = QPushButton("📊")  # Using emoji as placeholder
        thumb_button.setFixedSize(80, 60)
        thumb_button.setToolTip(f"Click to open {plot_data['title']}")
        thumb_button.clicked.connect(lambda: self._open_plot_popup(plot_data))
        
        # Create title label
        title_label = QLabel(plot_data['title'])
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setMaximumWidth(80)
        
        thumb_layout.addWidget(thumb_button)
        thumb_layout.addWidget(title_label)
        
        # Add to grid layout
        row = len(self.stored_plots) // 3
        col = (len(self.stored_plots) - 1) % 3
        self.plots_layout.addWidget(thumb_widget, row, col)

    def _refresh_thumbnails(self):
        """Refresh all thumbnails (for when plots are updated)."""
        # Clear existing thumbnails
        for i in reversed(range(self.plots_layout.count())):
            self.plots_layout.itemAt(i).widget().setParent(None)
        
        # Re-add all thumbnails
        for plot_data in self.stored_plots:
            self._add_plot_thumbnail(plot_data)

    def _open_plot_popup(self, plot_data):
        """Open a popup window for the selected plot, creating new windows for each plot."""
        plot_id = plot_data['id']
        
        # Check if a window for this plot already exists and is still open
        if plot_id in self.popup_windows:
            existing_popup = self.popup_windows[plot_id]
            if existing_popup and not existing_popup.isVisible():
                # Window was closed, remove from tracking
                del self.popup_windows[plot_id]
            elif existing_popup:
                # Window exists and is visible, just bring it to front
                existing_popup.show()
                existing_popup.raise_()
                existing_popup.activateWindow()
                return

        # Create a new popup window for this plot
        popup = ImagePlotWidget(
            self.project_context,
            plot_data['image_index'],
            isWindow=True,
            parent=self.parent_control_panel.parent() if self.parent_control_panel else self,
        )
        
        popup.setWindowTitle(f"Plot Manager - {plot_data['title']}")
        popup.resize(600, 400)
        
        # Set up cleanup when window is destroyed
        def cleanup_popup():
            if plot_id in self.popup_windows:
                del self.popup_windows[plot_id]
        
        popup.destroyed.connect(cleanup_popup)
        
        # Store reference to the popup
        self.popup_windows[plot_id] = popup
        
        # Update the plot with the coordinates
        x, y = plot_data['coords']
        if hasattr(popup, "showPixelSpectrum"):
            popup.showPixelSpectrum(x, y, plot_data['image_index'])
        
        # Show and bring to front
        popup.show()
        popup.raise_()
        popup.activateWindow()
    
    def closeEvent(self, event):
        """Clean up all popup windows when the tab is closed."""
        # Close all popup windows
        for popup in list(self.popup_windows.values()):
            if popup and popup.isVisible():
                popup.close()
        
        # Clear the tracking dict
        self.popup_windows.clear()
        
        super().closeEvent(event)

    def setup_view_click_handlers(self, raster_view):
        """Set up click handlers for different views."""
        self.raster_view = raster_view
        
        # Store original click handlers
        self._original_zoom_click = getattr(raster_view.zoomImage, 'mouseClickEvent', None)
        
        # Set up custom click handlers for each view
        if hasattr(raster_view, 'contextImage'):
            raster_view.contextImage.mouseClickEvent = lambda event: self._handle_context_click(event, raster_view)
        
        if hasattr(raster_view, 'mainImage'): 
            raster_view.mainImage.mouseClickEvent = lambda event: self._handle_main_click(event, raster_view)
            
        if hasattr(raster_view, 'zoomImage'):
            raster_view.zoomImage.mouseClickEvent = lambda event: self._handle_zoom_click(event, raster_view)

    def _handle_context_click(self, event, raster_view):
        """Handle clicks on context view."""
        if not self.context_enabled:
            return
            
        # Call original handling logic similar to zoom click
        self._process_click_event(event, raster_view, 'context')

    def _handle_main_click(self, event, raster_view):
        """Handle clicks on main view."""
        if not self.main_enabled:
            return
            
        self._process_click_event(event, raster_view, 'main')

    def _handle_zoom_click(self, event, raster_view):
        """Handle clicks on zoom view."""
        if not self.zoom_enabled:
            return
            
        # Call original zoom click logic
        if self._original_zoom_click:
            self._original_zoom_click(event)
        else:
            self._process_click_event(event, raster_view, 'zoom')

    def _process_click_event(self, event, raster_view, view_type):
        """Process click event for any view type."""
        from PyQt6.QtCore import Qt
        
        if event.button() == Qt.MouseButton.LeftButton:
            if view_type == 'zoom':
                # Use existing zoom logic
                pos = raster_view.zoomImage.mapFromScene(event.scenePos())
                x, y = int(pos.x()), int(pos.y())
                final_x, final_y = raster_view._zoomCoordsToAbsolute(x, y)
            else:
                # For context and main views, we need different coordinate mapping
                if view_type == 'context':
                    pos = raster_view.contextImage.mapFromScene(event.scenePos())
                    # Context coordinates are already in absolute image space
                    final_x, final_y = int(pos.x()), int(pos.y())
                elif view_type == 'main':
                    pos = raster_view.mainImage.mapFromScene(event.scenePos())
                    # Main coordinates need to be converted to absolute
                    final_x = int(raster_view.contextROI.pos().x() + pos.x())
                    final_y = int(raster_view.contextROI.pos().y() + pos.y())
            
            # Update crosshair if it's zoom view
            if view_type == 'zoom' and hasattr(raster_view, '_updateCrosshair'):
                raster_view._updateCrosshair(x, y)
            
            # Emit the click signal
            raster_view.sigImageClicked.emit(final_x, final_y)
            
        event.accept()

    def should_update_plot(self):
        """Check if plot updates should be processed based on current settings."""
        # Allow updates if any view is enabled
        return self.context_enabled or self.main_enabled or self.zoom_enabled


class ControlPanel(QWidget):
    """
    Control panel tied dynamically to the currently selected image.
    Now uses a tabbed interface with dockable tabs.
    """

    sigPixelPlotClicked = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex: int, rasterView, parent=None):
        super().__init__(parent)

        print("[DEBUG] 🔥 ControlPanel CLASS INSTANTIATED 🔥")

        self.project_context = proj
        self.imageIndex = imageIndex
        self.rasterView = rasterView

        self.setWindowTitle("Control Panel")
        self.resize(600, 400)

        # Store references to tabs for docking operations
        self.tabs: Dict[str, DockableTab] = {}

        # Initialize pixel plot tracking
        self.pixelPlotPopup = None
        self.lastPixelCoords = (0, 0)

        self.tabsDock = QDockWidget("Control Panel", self)
        self.dock_widget_content = QWidget()
        self._init_ui()
        self._setup_tabs()

        # Set the dock widget content
        self.tabsDock.setWidget(self.dock_widget_content)

        # Update the active image display immediately
        self.updateActiveImage(imageIndex)

        # Connect signals after everything is set up
        self._connect_signals()

    def _init_ui(self):
        """Initialize the main UI layout."""
        main_layout = QVBoxLayout(self.dock_widget_content)

        # Header section
        self.headerLabel = QLabel("Control Panel Menu")
        self.headerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headerLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 12px; color: gray;")

        # Tab widget
        self.tabWidget = QTabWidget()
        self.tabWidget.setTabsClosable(
            False
        )  # We'll add custom pop-out buttons instead

        # Add tab bar with pop-out buttons
        self._setup_tab_bar()

        main_layout.addWidget(self.headerLabel)
        main_layout.addWidget(self.activeImageLabel)
        main_layout.addWidget(self.tabWidget)

    def _setup_tab_bar(self):
        """Setup custom tab bar with pop-out functionality."""
        # We'll add right-click context menu for pop-out later
        self.tabWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabWidget.customContextMenuRequested.connect(self._show_tab_context_menu)

    def _setup_tabs(self):
        """Create and setup all tabs."""
        # Create tabs
        self.tabs["metadata"] = MetadataTab(self.project_context, self.imageIndex, self)
        self.tabs["roi"] = ROITab(
            self.project_context, self.imageIndex, self.rasterView, self
        )
        self.tabs["band"] = BandTab(self.project_context, self.imageIndex, self)
        self.tabs["stretch"] = StretchTab(
            self.project_context, self.imageIndex, self.rasterView, self
        )
        self.tabs["plot"] = PlotManagerTab(self.project_context, self.imageIndex, self)

        # Add tabs to widget
        for tab in self.tabs.values():
            self.tabWidget.addTab(tab, tab.title)

    def _connect_signals(self):
        """Connect all necessary signals."""
        # Connect raster view image click signal to update pixel plot
        if self.rasterView and hasattr(self.rasterView, "sigImageClicked"):
            self.rasterView.sigImageClicked.connect(self.updatePixelPlotFromCrosshair)
            print(
                "[DEBUG] Connected rasterView.sigImageClicked to updatePixelPlotFromCrosshair"
            )
            
        # Set up view-specific click handlers if plot manager exists
        if "plot" in self.tabs:
            plot_tab = self.tabs["plot"]
            if hasattr(plot_tab, 'setup_view_click_handlers'):
                plot_tab.setup_view_click_handlers(self.rasterView)

    def _show_tab_context_menu(self, position):
        """Show context menu for tab operations."""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction

        # Get the tab index at the clicked position
        tab_bar = self.tabWidget.tabBar()
        tab_index = tab_bar.tabAt(position)

        if tab_index == -1:
            return

        menu = QMenu(self)

        # Get the tab widget
        tab_widget = self.tabWidget.widget(tab_index)
        if isinstance(tab_widget, DockableTab):
            pop_out_action = QAction("Pop Out as Module", self)
            pop_out_action.triggered.connect(lambda: self._pop_out_tab(tab_index))
            menu.addAction(pop_out_action)

        menu.exec(self.tabWidget.mapToGlobal(position))

    def _pop_out_tab(self, tab_index):
        """Pop out a tab as a separate dockable module."""
        tab_widget = self.tabWidget.widget(tab_index)
        if isinstance(tab_widget, DockableTab):
            # Remove from tab widget first
            self.tabWidget.removeTab(tab_index)
            # Then pop out
            tab_widget.pop_out()

    def updateActiveImage(self, imageIndex):
        """Update the active image display."""
        self.imageIndex = imageIndex
        if imageIndex is not None:
            try:
                image = self.project_context.getImage(imageIndex)
                if image and hasattr(image, "metadata") and image.metadata:
                    # Truncate long names
                    name = image.metadata.name
                    if len(name) > 20:
                        name = name[:17] + "..."
                    self.activeImageLabel.setText(f"Active Image: {name}")
                    print(f"[DEBUG] Updated active image label to: {name}")
                else:
                    self.activeImageLabel.setText(f"Active Image: Image {imageIndex}")
                    print(f"[DEBUG] Updated active image label to: Image {imageIndex}")
            except Exception as e:
                print(f"[DEBUG] Error updating active image: {e}")
                self.activeImageLabel.setText(f"Active Image: Image {imageIndex}")
        else:
            self.activeImageLabel.setText("No image selected")

    def updatePixelPlotFromCrosshair(self, x, y):
        """Update pixel plot from crosshair position."""
        print(f"[DEBUG] updatePixelPlotFromCrosshair called with coords: ({x}, {y})")
        self.lastPixelCoords = (x, y)

        # Check if plot manager allows this update
        if "plot" in self.tabs:
            plot_tab = self.tabs["plot"]
            if hasattr(plot_tab, 'should_update_plot'):
                if not plot_tab.should_update_plot():
                    print(f"[DEBUG] Plot update blocked by Plot Manager settings")
                    return

        # Update the plot tab using the correct method
        if "plot" in self.tabs:
            plot_tab = self.tabs["plot"]
            if hasattr(plot_tab, "showPixelSpectrum"):
                plot_tab.showPixelSpectrum(x, y)
            elif hasattr(plot_tab, "pixelPlot") and hasattr(
                plot_tab.pixelPlot, "showPixelSpectrum"
            ):
                plot_tab.pixelPlot.showPixelSpectrum(x, y)
            print(f"[DEBUG] Updated plot tab with coordinates")

        # Also update popup if it exists
        if self.pixelPlotPopup and hasattr(self.pixelPlotPopup, "showPixelSpectrum"):
            self.pixelPlotPopup.showPixelSpectrum(x, y)

    def handlePixelPlotClicked(self):
        """Handle pixel plot click - create popup for current embedded plot."""
        # Get the current coordinates from the embedded plot
        x, y = self.lastPixelCoords
        
        # Create a unique plot data entry for the current embedded plot
        # Use a timestamp to ensure uniqueness
        import time
        current_plot_id = f"current_plot_{int(time.time() * 1000)}"
        
        current_plot_data = {
            'id': current_plot_id,
            'coords': (x, y),
            'image_index': self.imageIndex,
            'title': f"Current Pixel ({x}, {y})"
        }
        
        # Use the same popup method as thumbnails
        self._open_plot_popup(current_plot_data)
