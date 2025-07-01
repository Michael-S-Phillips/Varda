"""
General Image Analysis Workflow

A comprehensive workflow for performing general image analysis with integrated
ROI drawing, band selection, stretch controls, and metadata management.
"""

import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QDockWidget,
    QVBoxLayout,
    QWidget,
    QStatusBar,
)
from PyQt6.QtCore import Qt, pyqtSignal

import varda
from varda.core.entities import ROIMode

from varda.features.components.band_management.band_manager import BandManager
from varda.features.image_view_roi import getROIView
from varda.features.components.raster_view.triple_raster_view import TripleRasterView
from varda.features.components import roi_drawing

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

        self.imageIndex = imageIndex
        self.image = varda.app.proj.getImage(imageIndex)
        self.project = varda.app.proj

        # Initialize core components
        self.rasterView = None
        self.roiAdapter = None
        self.roiView = None
        self.bandView = None
        self.stretchView = None

        # Initialize UI and connections
        self._initComponents()
        self._initUI()
        self._connectSignals()

        self.showMaximized()

        self.setStatusMessage(
            f"General Image Analysis Workflow initialized for image {imageIndex}"
        )
        self.drawingController = roi_drawing.ROIDrawingControllerNew()

        self.drawingController.startDrawing(
            ROIMode.FREEHAND, self.tripleRasterView.viewport1
        )

    def _initComponents(self):
        """Initialize all workflow components"""

        # Initialize raster view
        self.tripleRasterView = TripleRasterView(self.imageIndex, self.project, self)
        # self.rasterView = varda.features.image_view_raster.getRasterView(
        #     self.project, self.imageIndex, self
        # )

        # Initialize band selection view
        self.bandView = BandManager(self.project, self.imageIndex, self)

        # Initialize stretch controls
        self.stretchView = varda.features.image_view_stretch.StretchManager(
            self.project, self.imageIndex, self
        )

        # Initialize ROI view/table
        self.roiView = getROIView(self.project, self.imageIndex, self)

    def _initUI(self):
        """Initialize the user interface for the workflow"""
        self.setWindowTitle(f"General Image Analysis - Image {self.imageIndex}")

        # Set the raster view as the central widget
        self.setCentralWidget(self.tripleRasterView)

        # Create dock widgets for controls
        self._setupDockWidgets()

        self.setStatusBar(QStatusBar(self))

    def _setupDockWidgets(self):
        """Setup dock widgets for the various control panels"""

        # ROI Management Dock (left side)
        roiDock = QDockWidget("ROI Management", self)
        roiDock.setWidget(self.roiView)
        roiDock.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, roiDock)

        # Image Controls Dock (right side - contains band and stretch controls)
        imageControlsWidget = QWidget()
        imageControlsLayout = QVBoxLayout(imageControlsWidget)

        # Add band controls
        imageControlsLayout.addWidget(self.bandView)

        # Add stretch controls
        imageControlsLayout.addWidget(self.stretchView)

        imageControlsDock = QDockWidget("Image Controls", self)
        imageControlsDock.setWidget(imageControlsWidget)
        imageControlsDock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, imageControlsDock)

    def _connectSignals(self):
        """Connect signals between workflow components"""

        # Connect basic image display signals
        # self.bandView.sigBandChanged.connect(self.rasterView.selectBand)
        # self.stretchView.sigStretchSelected.connect(self.rasterView.selectStretch)

        logger.debug("All workflow signals connected")

    def setStatusMessage(self, message):
        """Set a status message in the status bar"""
        self.statusBar().showMessage(message)

    def closeEvent(self, event):
        """Handle workflow closure"""
        self.workflowClosed.emit()  # Emit signal before closing
        super().closeEvent(event)
