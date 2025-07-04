import logging
from typing import Dict

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QDockWidget,
    QLabel,
    QWidget,
    QPushButton,
    QTabWidget,
    QMainWindow,
)
from PyQt6.QtCore import Qt, pyqtSignal
import numpy as np

from varda.core.data import ProjectContext
from varda.core.entities import Band, Stretch
from varda.features.image_view_roi import getROIView
from varda.features.components.band_management.band_manager import BandManager
from varda.features.image_view_stretch import StretchManager
from varda.features.image_view_metadata import openMetadataEditor
from varda.gui.widgets.detachable_tab_widget import DetachableTabWidget
from varda.gui.widgets.image_plot_widget import ImagePlotWidget

# from varda.gui.widgets.plot_manager_tab import PlotManagerTab

logger = logging.getLogger(__name__)


class DockableTab(QWidget):
    """Base class for tabs that can be docked as separate modules."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.parent_control_panel = parent
        self.dockedWidget = None
        # Override minimum width constraints
        self.setMinimumWidth(20)  # Set minimum width
        self.setMinimumHeight(20)  # Set minimum height

    # def popOut(self):
    #     """Pop this tab out as a separate dockable widget."""
    #     if self.dockedWidget is not None:
    #         return  # Already popped out
    #
    #     # Create a new dock widget
    #     self.dockedWidget = QDockWidget(self.title, self.parent_control_panel)
    #     self.dockedWidget.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    #
    #     # Remove from tab widget and add to dock
    #     if self.parent():
    #         self.setParent(None)
    #     self.dockedWidget.setWidget(self)
    #
    #     # Add to main window
    #     self.mainWindow.addDockWidget(
    #         Qt.DockWidgetArea.RightDockWidgetArea, self.dockedWidget
    #     )
    #
    #     # Connect close event to return to tab
    #     self.dockedWidget.visibilityChanged.connect(self._on_dock_visibility_changed)
    #
    # def _on_dock_visibility_changed(self, visible):
    #     """Handle when the docked widget is closed."""
    #     if not visible and self.dockedWidget:
    #         self.dockIn()
    #
    # def dockIn(self):
    #     """Return this tab to the control panel."""
    #     if self.dockedWidget is None:
    #         return
    #
    #     # Remove from dock widget
    #     self.dockedWidget.setWidget(None)
    #     self.dockedWidget.close()
    #     self.dockedWidget = None
    #
    #     # Add back to tab widget
    #     if self.parent_control_panel and hasattr(
    #         self.parent_control_panel, "tabWidget"
    #     ):
    #         self.parent_control_panel.tabWidget.addTab(self, self.title)


class MetadataTab(DockableTab):
    """Tab for metadata editing functionality."""

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Metadata", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self._initUI()

    def _initUI(self):
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

    sigBandChanged = pyqtSignal(Band)

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Band Selection", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        self.bandManager = BandManager(self.project_context, self.imageIndex, self)
        self.bandManager.sigBandChanged.connect(self.sigBandChanged)
        layout.addWidget(self.bandManager)


class StretchTab(DockableTab):
    """Tab for stretch options functionality."""

    sigStretchChanged = pyqtSignal(Stretch)

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__("Stretch Options", parent)
        self.project_context = proj
        self.imageIndex = imageIndex
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)

        self.stretchManager = StretchManager(
            self.project_context, self.imageIndex, self
        )
        self.stretchManager.sigStretchChanged.connect(self.sigStretchChanged)
        layout.addWidget(self.stretchManager)


class ControlPanel(QWidget):
    """
    Control panel tied dynamically to the currently selected image.
    Now uses a tabbed interface with dockable tabs.
    """

    sigPixelPlotClicked = pyqtSignal()
    sigBandChanged = pyqtSignal(Band)
    sigStretchChanged = pyqtSignal(Stretch)

    def __init__(
        self,
        proj: ProjectContext,
        imageIndex: int,
        mainWindow: QMainWindow,
        parent=None,
    ):
        super().__init__(parent)

        self.proj = proj
        self.imageIndex = imageIndex
        self.mainWindow = mainWindow

        self.setWindowTitle("Control Panel")
        self.resize(600, 400)

        # Store references to tabs for docking operations
        self.tabs: Dict[str, DockableTab] = {}

        # Initialize pixel plot tracking
        self.pixelPlotPopup = None
        self.lastPixelCoords = (0, 0)

        # self.tabsDock = QDockWidget("Control Panel", self)
        # self.dockWidgetContent = QWidget()
        self._initUI()
        self._setupTabs()

        # Set the dock widget content
        # self.tabsDock.setWidget(self.dockWidgetContent)

        # Update the active image display immediately
        self.updateActiveImage(imageIndex)

        # Connect signals after everything is set up
        self._connectSignals()

    def _initUI(self):
        """Initialize the main UI layout."""
        # main_layout = QVBoxLayout(self.dockWidgetContent)

        # Header section
        self.headerLabel = QLabel("Control Panel Menu")
        self.headerLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headerLabel.setStyleSheet("font-size: 14px; font-weight: bold;")

        self.activeImageLabel = QLabel("No image selected")
        self.activeImageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activeImageLabel.setStyleSheet("font-size: 12px; color: gray;")

        # Tab widget
        # self.detachableTabWidget = DetachableTabWidget(self)
        # self.tabWidget = QTabWidget()
        # self.tabWidget.setTabsClosable(
        #     False
        # )  # We'll add custom pop-out buttons instead

        # Add tab bar with pop-out buttons
        # self._setupTabBar()

        # main_layout.addWidget(self.headerLabel)
        # main_layout.addWidget(self.activeImageLabel)
        # main_layout.addWidget(self.detachableTabWidget)
        # self.setLayout(main_layout)

    # def _setupTabBar(self):
    #     """Setup custom tab bar with pop-out functionality."""
    #     # We'll add right-click context menu for pop-out later
    #     self.tabWidget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    #     self.tabWidget.customContextMenuRequested.connect(self._showTabContextMenu)

    def _setupTabs(self):
        """Create and setup all tabs."""

        # Create tabs
        self.tabs["metadata"] = MetadataTab(self.proj, self.imageIndex, self)
        self.tabs["band"] = BandTab(self.proj, self.imageIndex, self)
        self.tabs["stretch"] = StretchTab(self.proj, self.imageIndex, self)

        # commented out until i update them
        # self.tabs["roi"] = ROITab(
        #     self.project_context, self.imageIndex, self.rasterView, self
        # )
        # self.tabs["plot"] = PlotManagerTab(self.proj, self.imageIndex, self)

        # Add create dockable tabs
        prevDock = None
        for tab in self.tabs.values():
            dock = QDockWidget(tab.title)
            dock.setWidget(tab)
            self.mainWindow.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
            if prevDock is not None:
                self.mainWindow.tabifyDockWidget(prevDock, dock)
            prevDock = dock
        self.mainWindow.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )
        # self.detachableTabWidget.addTab(tab, tab.title)

    def _connectSignals(self):
        """Connect all necessary signals."""
        self.tabs["band"].sigBandChanged.connect(self.sigBandChanged)
        self.tabs["stretch"].sigStretchChanged.connect(self.sigStretchChanged)

    # Set up view-specific click handlers if plot manager exists
    # if "plot" in self.tabs:
    #     plot_tab = self.tabs["plot"]
    #     if hasattr(plot_tab, "setup_view_click_handlers"):
    #         plot_tab.setup_view_click_handlers(self.rasterView)
    #
    # def _showTabContextMenu(self, position):
    #     """Show context menu for tab operations."""
    #     from PyQt6.QtWidgets import QMenu
    #     from PyQt6.QtGui import QAction
    #
    #     # Get the tab index at the clicked position
    #     tab_bar = self.tabWidget.tabBar()
    #     tab_index = tab_bar.tabAt(position)
    #
    #     if tab_index == -1:
    #         return
    #
    #     menu = QMenu(self)
    #
    #     # Get the tab widget
    #     tab_widget = self.tabWidget.widget(tab_index)
    #     if isinstance(tab_widget, DockableTab):
    #         pop_out_action = QAction("Pop Out as Module", self)
    #         pop_out_action.triggered.connect(lambda: self._popOutTab(tab_index))
    #         menu.addAction(pop_out_action)
    #
    #     menu.exec(self.tabWidget.mapToGlobal(position))
    #
    # def _popOutTab(self, tab_index):
    #     """Pop out a tab as a separate dockable module."""
    #     tab_widget = self.tabWidget.widget(tab_index)
    #     if isinstance(tab_widget, DockableTab):
    #         # Remove from tab widget first
    #         self.tabWidget.removeTab(tab_index)
    #         # Then pop out
    #         tab_widget.popOut()

    def updateActiveImage(self, imageIndex):
        """Update the active image display."""
        self.imageIndex = imageIndex
        if imageIndex is not None:
            image = self.proj.getImage(imageIndex)
            # Truncate long names
            name = image.metadata.name
            if len(name) > 20:
                name = name[:17] + "..."
            self.activeImageLabel.setText(f"Active Image: {name}")
        else:
            self.activeImageLabel.setText("No image selected")

    def updatePixelPlotFromCrosshair(self, x, y):
        """Update pixel plot from crosshair position."""
        print(f"[DEBUG] updatePixelPlotFromCrosshair called with coords: ({x}, {y})")
        self.lastPixelCoords = (x, y)

        # Check if plot manager allows this update
        if "plot" in self.tabs:
            plot_tab = self.tabs["plot"]
            if hasattr(plot_tab, "should_update_plot"):
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
            "id": current_plot_id,
            "coords": (x, y),
            "image_index": self.imageIndex,
            "title": f"Current Pixel ({x}, {y})",
        }

        # Use the same popup method as thumbnails
        self.tabs["plot"]._open_plot_popup(current_plot_data)
