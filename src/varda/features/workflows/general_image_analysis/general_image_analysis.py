"""
General Image Analysis Workflow

A comprehensive workflow for performing general image analysis with integrated
ROI drawing, band selection, stretch controls, and metadata management.
"""

import logging
from typing import Optional

from PyQt6.QtWidgets import QMainWindow, QDockWidget, QVBoxLayout, QWidget, QSplitter
from PyQt6.QtCore import Qt, pyqtSignal

import varda
from varda.features.components.roi_drawing.raster_view_roi_adapter import (
    RasterViewROIAdapter,
)
from varda.features.components.roi_drawing.roi_drawing_controller import (
    ROIDrawingConfig,
)
from varda.features.image_view_roi.enhanced_roi_view import getROIView
from varda.features.image_view_roi.roi_viewmodel import ROIViewModel

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
    roiCreated = pyqtSignal(object)  # Emitted when a new ROI is created
    roiSelected = pyqtSignal(str)  # Emitted when an ROI is selected
    workflowClosed = pyqtSignal()  # Emitted when workflow is closed

    def __init__(self, imageIndex=0, parent=None):
        super().__init__(parent)

        self.imageIndex = imageIndex
        self.project = varda.app.proj

        # Initialize core components
        self.rasterView = None
        self.roiAdapter = None
        self.roiView = None
        self.bandView = None
        self.stretchView = None

        # Initialize UI and connections
        self.initComponents()
        self.initUI()
        self.connectWorkflowSignals()

        self.showMaximized()

        logger.info(
            f"General Image Analysis Workflow initialized for image {imageIndex}"
        )

    def initComponents(self):
        """Initialize all workflow components"""

        # Initialize raster view
        self.rasterView = varda.features.image_view_raster.getRasterView(
            self.project, self.imageIndex, self
        )

        # Initialize band selection view
        self.bandView = varda.features.image_view_band.getBandView(
            self.project, self.imageIndex, self
        )

        # Initialize stretch controls
        self.stretchView = varda.features.image_view_stretch.StretchManager(
            self.project, self.imageIndex, self
        )

        # Initialize ROI drawing adapter with custom configuration
        roiConfig = ROIDrawingConfig(
            enableToolbar=True,
            toolbarTitle="ROI Drawing Tools",
            defaultMode=varda.gui.widgets.roi_selector.ROIMode.FREEHAND,
        )

        self.roiAdapter = RasterViewROIAdapter(
            self.rasterView,
            self.rasterView.viewModel,  # Use the raster view's view model
            roiConfig,
        )

        # Initialize enhanced ROI view/table
        self.roiView = getROIView(self.project, self.imageIndex, self)

        logger.debug("All workflow components initialized")

    def initUI(self):
        """Initialize the user interface for the workflow"""
        self.setWindowTitle(f"General Image Analysis - Image {self.imageIndex}")

        # Set the raster view as the central widget
        self.setCentralWidget(self.rasterView)

        # Create dock widgets for controls
        self.setupDockWidgets()

        # Add ROI drawing toolbar to the main window
        roiToolbar = self.roiAdapter.getToolbar()
        if roiToolbar:
            self.addToolBar(Qt.ToolBarArea.TopToolBarArea, roiToolbar)

    def setupDockWidgets(self):
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

    def connectWorkflowSignals(self):
        """Connect signals between workflow components"""

        # Connect basic image display signals
        self.bandView.sigBandChanged.connect(self.rasterView.selectBand)
        self.stretchView.sigStretchSelected.connect(self.rasterView.selectStretch)

        # Connect ROI drawing signals
        self.connectROIDrawingSignals()

        # Connect ROI table/view signals
        self.connectROIViewSignals()

        logger.debug("All workflow signals connected")

    def connectROIDrawingSignals(self):
        """Connect ROI drawing related signals"""

        # Connect ROI adapter signals to workflow
        self.roiAdapter.roiCreated.connect(self.onRoiCreated)
        self.roiAdapter.roiSelected.connect(self.onRoiSelected)

        # Connect the ROI view's draw button to start drawing
        if hasattr(self.roiView, "draw_roi_button"):
            self.roiView.draw_roi_button.clicked.connect(self.startDrawingROI)

        # Connect ROI drawing controller signals for status updates
        if hasattr(self.roiAdapter, "drawingController"):
            controller = self.roiAdapter.drawingController
            controller.statusMessageChanged.connect(self.updateStatusMessage)
            controller.drawingModeChanged.connect(self.onDrawingModeChanged)

        logger.debug("ROI drawing signals connected")

    def connectROIViewSignals(self):
        """Connect ROI view/table related signals"""

        # Connect ROI selection from the table to highlight in raster view
        self.roiView.roiSelectionChanged.connect(self.onRoiTableSelectionChanged)

        # Connect ROI view model signals to refresh the table
        if hasattr(self.roiView, "viewModel"):
            viewModel = self.roiView.viewModel

            # Set the raster view reference for coordination
            if hasattr(viewModel, "setRasterView"):
                viewModel.setRasterView(self.rasterView)

        logger.debug("ROI view signals connected")

    def startDrawingROI(self):
        """Start drawing a new ROI"""
        try:
            success = self.roiAdapter.startDrawingRoi()
            if success:
                logger.info("Started ROI drawing")
                self.updateStatusMessage("ROI drawing started")
            else:
                logger.warning("Failed to start ROI drawing")
                self.updateStatusMessage("Failed to start ROI drawing")
        except Exception as e:
            logger.error(f"Error starting ROI drawing: {e}")
            self.updateStatusMessage("Error starting ROI drawing")

    def cancelDrawingROI(self):
        """Cancel any active ROI drawing"""
        try:
            self.roiAdapter.cancelDrawing()
            logger.info("ROI drawing canceled")
            self.updateStatusMessage("ROI drawing canceled")
        except Exception as e:
            logger.error(f"Error canceling ROI drawing: {e}")

    def onRoiCreated(self, roi):
        """Handle creation of a new ROI"""
        try:
            logger.info(f"ROI created in workflow: {roi}")

            # Refresh the ROI table to show the new ROI
            if hasattr(self.roiView, "updateROITable"):
                self.roiView.updateROITable()

            # Emit workflow-level signal
            self.roiCreated.emit(roi)

            self.updateStatusMessage(f"ROI created successfully")

        except Exception as e:
            logger.error(f"Error handling ROI creation: {e}")
            self.updateStatusMessage("Error handling ROI creation")

    def onRoiSelected(self, roiId):
        """Handle ROI selection from drawing"""
        try:
            logger.debug(f"ROI selected from drawing: {roiId}")
            self.roiSelected.emit(roiId)
        except Exception as e:
            logger.error(f"Error handling ROI selection: {e}")

    def onRoiTableSelectionChanged(self, roiIndex):
        """Handle ROI selection from the table"""
        try:
            logger.debug(f"ROI selected from table: {roiIndex}")

            # Highlight the ROI in the raster view
            if hasattr(self.rasterView, "highlightROI"):
                self.rasterView.highlightROI(roiIndex)

            # Emit workflow-level signal with ROI index converted to ID
            self.roiSelected.emit(str(roiIndex))

        except Exception as e:
            logger.error(f"Error handling ROI table selection: {e}")

    def onDrawingModeChanged(self, mode):
        """Handle drawing mode changes"""
        try:
            modeNames = ["Freehand", "Rectangle", "Ellipse", "Polygon"]
            modeName = modeNames[mode] if mode < len(modeNames) else "Unknown"
            logger.debug(f"Drawing mode changed to: {modeName}")
            self.updateStatusMessage(f"Drawing mode: {modeName}")
        except Exception as e:
            logger.error(f"Error handling drawing mode change: {e}")

    def updateStatusMessage(self, message):
        """Update status message (can be expanded to use status bar)"""
        # For now, just log the message
        # In the future, this could update a status bar
        logger.info(f"Workflow status: {message}")

    def getROIDrawingController(self):
        """Get the ROI drawing controller for external access"""
        if self.roiAdapter:
            return self.roiAdapter.drawingController
        return None

    def getRasterView(self):
        """Get the raster view for external access"""
        return self.rasterView

    def getROIView(self):
        """Get the ROI view for external access"""
        return self.roiView

    def isDrawingActive(self):
        """Check if ROI drawing is currently active"""
        if self.roiAdapter:
            return self.roiAdapter.isDrawingActive()
        return False

    def setDrawingMode(self, mode):
        """Set the ROI drawing mode"""
        if self.roiAdapter:
            self.roiAdapter.setDrawingMode(mode)

    def getDrawingMode(self):
        """Get the current ROI drawing mode"""
        if self.roiAdapter:
            return self.roiAdapter.getDrawingMode()
        return None

    def showAllROIs(self):
        """Show all ROIs in the view"""
        if self.rasterView and hasattr(self.rasterView, "draw_all_polygons"):
            self.rasterView.draw_all_polygons()
        self.updateStatusMessage("All ROIs visible")

    def hideAllROIs(self):
        """Hide all ROIs in the view"""
        if self.rasterView and hasattr(self.rasterView, "remove_polygons_from_display"):
            self.rasterView.remove_polygons_from_display()
        self.updateStatusMessage("All ROIs hidden")

    def closeEvent(self, event):
        """Handle workflow closure"""
        try:
            # Cancel any active drawing
            if self.isDrawingActive():
                self.cancelDrawingROI()

            # Clean up ROI adapter
            if self.roiAdapter:
                self.roiAdapter.cleanup()

            # Emit workflow closed signal
            self.workflowClosed.emit()

            logger.info("General Image Analysis Workflow closed")

        except Exception as e:
            logger.error(f"Error during workflow closure: {e}")

        super().closeEvent(event)
