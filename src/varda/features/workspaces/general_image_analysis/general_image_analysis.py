"""
General Image Analysis Workflow

A comprehensive workflow for performing general image analysis with integrated
ROI drawing, band selection, stretch controls, and metadata management.
"""

import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QStatusBar,
    QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

import varda
from varda.image_rendering.band_management.band_manager import BandManager
from varda.features.components.metadata_management.metadata_editor import MetadataEditor
from varda.features.components.raster_view.roi_display_controller import (
    ROIDisplayController,
)
from varda.features.components.rois.roi_manager_widget import ROIManagerWidget
from varda.image_rendering.stretch_management_and_histogram import (
    StretchManager,
)
from varda.features.image_view_roi import getROIView
from varda.features.components.raster_view import TripleRasterView
from varda.features.components.viewport_tools.tool_manager import (
    ToolManager,
)
from varda.gui.widgets.varda_dock_widget import VardaDockWidget

logger = logging.getLogger(__name__)


class GeneralImageAnalysisWorkflow(QMainWindow):
    """
    A workflow for performing general image analysis with integrated ROI functionality.

    This workflow orchestrates:
    - Raster image display with navigation
    - ROI drawing and management
    - Band selection controls
    - Stretch/contrast controls
    - Metadata editing
    """

    # Workflow-level signals
    workflowClosed: pyqtSignal = pyqtSignal()  # Emitted when workflow is closed

    def __init__(self, imageIndex=0, parent=None):
        super().__init__(parent)
        # self.viewModel = GeneralPurposeImageViewModel(self)
        # self.viewModel.imageIndex = imageIndex
        # self.image = self.viewModel.getImage()
        self.imageIndex = imageIndex
        self.image = varda.app.proj.getImage(imageIndex)
        self.project = varda.app.proj

        # Initialize core components
        self.rasterView = None
        self.roiAdapter = None
        self.roiManager = None
        self.bandManager = None
        self.stretchManager = None

        # Initialize UI and connections
        self._initComponents()
        self._initUI()
        self._setupDocks()
        self._connectSignals()

        self.showMaximized()

        self.setStatusMessage(
            f"General Image Analysis Workflow initialized for image {imageIndex}"
        )

    def _initComponents(self):
        """Initialize all workflow components"""

        # Initialize raster view
        self.tripleRasterView = TripleRasterView(self.imageIndex, self.project, self)

        # Initialize tool management for each viewport
        self.toolManager1 = ToolManager(self.tripleRasterView.viewport1, self)
        self.toolManager2 = ToolManager(self.tripleRasterView.viewport2, self)
        self.toolManager3 = ToolManager(self.tripleRasterView.viewport3, self)

        # Create toolbars for each viewport
        self.tripleRasterView.viewport1.addToolBar(self.toolManager1.getToolbar())
        self.tripleRasterView.viewport2.addToolBar(self.toolManager2.getToolbar())
        self.tripleRasterView.viewport3.addToolBar(self.toolManager3.getToolbar())

        # Initialize band selection view
        self.bandManager = BandManager(self.project, self.imageIndex, self)

        # Initialize stretch controls
        self.stretchManager = StretchManager(self.project, self.imageIndex, self)

        # Initialize metadata editor
        self.metadataEditor = MetadataEditor(self.project, self.imageIndex, self)

        # Initialize ROI view/table
        self.roiManager = ROIManagerWidget(self.project, self.imageIndex, self)
        displayController: ROIDisplayController = self.roiManager.getDisplayController()

        displayController.registerViewport(
            "viewport 1", self.tripleRasterView.viewport1
        )
        displayController.registerViewport(
            "viewport 2", self.tripleRasterView.viewport2
        )
        displayController.registerViewport(
            "viewport 3", self.tripleRasterView.viewport3
        )
        self.oldRoiView = getROIView(self.project, self.imageIndex, self)

    def _initUI(self):
        """Initialize the user interface for the workflow"""
        self.setWindowTitle(f"General Image Analysis - Image {self.imageIndex}")

        # Set the raster view as the central widget
        self.setCentralWidget(self.tripleRasterView)

        self.setStatusBar(QStatusBar(self))

    def _setupDocks(self):
        """Setup all of the dock widgets for the workflow. This is most of the viewport_tools"""
        docks = []
        loc = Qt.DockWidgetArea.LeftDockWidgetArea
        bandDock = VardaDockWidget("Band Manager", self.bandManager, loc, self)
        docks.append(bandDock)

        stretchDock = VardaDockWidget("Stretch Manager", self.stretchManager, loc, self)
        docks.append(stretchDock)

        metadataDock = VardaDockWidget("Metadata", self.metadataEditor, loc, self)
        docks.append(metadataDock)

        roiDock = VardaDockWidget("ROI Manager", self.roiManager, loc, self)
        docks.append(roiDock)

        oldRoiDock = VardaDockWidget("Old ROI View", self.oldRoiView, loc, self)
        docks.append(oldRoiDock)

        # stack docks
        self.tabifyDockWidget(bandDock, stretchDock)
        self.tabifyDockWidget(stretchDock, roiDock)
        self.tabifyDockWidget(roiDock, metadataDock)
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )

    def _connectSignals(self):
        """Connect signals between workflow components"""
        self.bandManager.sigBandChanged.connect(self.tripleRasterView.setBand)
        self.stretchManager.sigStretchChanged.connect(self.tripleRasterView.setStretch)

    def setStatusMessage(self, message):
        """Set a status message in the status bar"""
        self.statusBar().showMessage(message)

    def closeEvent(self, event):
        """Handle workflow closure"""
        self.workflowClosed.emit()  # Emit signal before closing
        super().closeEvent(event)
