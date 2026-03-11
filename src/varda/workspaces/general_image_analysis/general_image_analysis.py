"""
General Image Analysis Workflow

A comprehensive workflow for performing general image analysis with integrated
ROI drawing, band selection, stretch controls, and metadata management.
"""

import logging

from PyQt6.QtWidgets import (
    QMainWindow,
    QStatusBar,
)
from pyqtgraph.dockarea import DockArea, Dock

from varda.common.entities import VardaRaster
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import (
    NewHistogramView,
)
from varda.image_rendering.raster_view import TripleRasterView, ROIDisplayController
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.common.parameter import ImageParameter, ParameterGroup
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget

logger = logging.getLogger(__name__)


class GeneralImageAnalysisConfig(ParameterGroup):
    image = ImageParameter(
        "Image",
        "The image to view.",
    )

    def __init__(self, imageList: list[VardaRaster]) -> None:
        super().__init__()
        self.imageList = imageList
        self.image.setProvider(lambda: self.imageList)


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

    def __init__(self, config: GeneralImageAnalysisConfig, parent=None):
        super().__init__(parent)
        self.config = config

        # Initialize core components
        self.rasterView = None
        self.bandManager = None
        self.stretchManager = None

        # Initialize UI and connections
        self._initComponents()
        self._initUI()
        self._connectSignals()

        self.showMaximized()

        self.setStatusMessage("General Image Analysis Workflow initialized")

    def _initComponents(self):
        """Initialize all workflow components"""

        # Initialize raster view
        self.imageRenderer = ImageRenderer(image=self.config.image.value)

        self.rendererSettingsPanel = self.imageRenderer.getSettingsPanel()

        self.tripleRasterView = TripleRasterView(self.imageRenderer, self)

        # Initialize tool management for each viewport
        self.toolManager1 = ToolManager(self.tripleRasterView.viewport1, self)
        self.toolManager2 = ToolManager(self.tripleRasterView.viewport2, self)
        self.toolManager3 = ToolManager(self.tripleRasterView.viewport3, self)

        # Create toolbars for each viewport
        self.tripleRasterView.viewport1.addToolBar(self.toolManager1.getToolbar())
        self.tripleRasterView.viewport2.addToolBar(self.toolManager2.getToolbar())
        self.tripleRasterView.viewport3.addToolBar(self.toolManager3.getToolbar())

        # initialize histogram view
        self.histogram = NewHistogramView(self.imageRenderer, self)

        # --- ROI system ---
        image = self.config.image.value
        self.roiCollection = ROICollection.fromImage(image)

        self.roiDisplayController = ROIDisplayController(
            self.roiCollection, image, parent=self
        )
        self.roiDisplayController.registerViewport(
            "viewport1", self.tripleRasterView.viewport1
        )
        self.roiDisplayController.registerViewport(
            "viewport2", self.tripleRasterView.viewport2
        )
        self.roiDisplayController.registerViewport(
            "viewport3", self.tripleRasterView.viewport3
        )

        self.roiManagerWidget = ROIManagerWidget(self.roiCollection, parent=self)

    def _initUI(self):
        """Initialize the user interface for the workflow"""
        self.setWindowTitle(
            f"General Image Analysis - Image {self.config.image.value.name}"
        )

        self._setupDocks()
        # Set the raster view as the central widget
        # self.setCentralWidget(self.tripleRasterView)

        self.setStatusBar(QStatusBar(self))

    def _setupDocks(self):
        """Setup all of the dock widgets for the workflow. This is most of the viewport_tools"""
        dockArea = DockArea(self)
        self.setCentralWidget(dockArea)
        docks = []

        rasterDock = Dock("Raster Dock", widget=self.tripleRasterView, size=(800, 800))
        docks.append(rasterDock)

        settingsDock = Dock(
            "Render Settings", widget=self.rendererSettingsPanel, size=(100, 100)
        )
        docks.append(settingsDock)

        histogramDock = Dock("Histogram Dock", widget=self.histogram)
        docks.append(histogramDock)
        # bandDockNew = Dock("Band Dock", widget=self.bandManager)
        # docks.append(bandDockNew)
        # bandDock = VardaDockWidget("Band Manager", self.bandManager, loc, self)
        # docks.append(bandDock)

        # stretchDockNew = Dock("Stretch Dock", widget=self.stretchManager)
        # docks.append(stretchDockNew)
        # stretchDock = VardaDockWidget("Stretch Manager", self.stretchManager, loc, self)
        # docks.append(stretchDock)

        # metadataDockNew = Dock("Metadata Dock", widget=self.metadataEditor)
        # docks.append(metadataDockNew)
        # metadataDock = VardaDockWidget("Metadata", self.metadataEditor, loc, self)
        # docks.append(metadataDock)

        roiDockNew = Dock("ROI Dock", widget=self.roiManagerWidget, size=(100, 100))
        docks.append(roiDockNew)
        # roiDock = VardaDockWidget("ROI Manager", self.roiManager, loc, self)
        # docks.append(roiDock)

        # oldRoiDockNew = Dock("Old ROI Dock", widget=self.oldRoiView)
        # docks.append(oldRoiDockNew)
        # oldRoiDock = VardaDockWidget("Old ROI View", self.oldRoiView, loc, self)
        # docks.append(oldRoiDock)

        # stack docks
        # self.tabifyDockWidget(bandDock, stretchDock)
        # self.tabifyDockWidget(stretchDock, roiDock)
        # self.tabifyDockWidget(roiDock, metadataDock)
        # self.setTabPosition(
        #    Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        # )
        dockArea.addDock(rasterDock, "right")
        dockArea.addDock(settingsDock, "left")
        dockArea.addDock(roiDockNew, "bottom", settingsDock)
        dockArea.addDock(histogramDock, "bottom", roiDockNew)
        # dockArea.addDock(bandDockNew, "left")
        # dockArea.addDock(stretchDockNew, "below", bandDockNew)
        # dockArea.addDock(metadataDockNew, "bottom")
        # dockArea.addDock(oldRoiDockNew, "below", roiDockNew)

    def _connectSignals(self):
        """Connect signals between workflow components"""
        self.rendererSettingsPanel.sigSettingsChanged.connect(
            self.imageRenderer.updateSettings
        )

        # Wire ROI drawing tools to collection via ToolManager signals
        for tm in (self.toolManager1, self.toolManager2, self.toolManager3):
            tm.sigToolActivated.connect(self._onToolActivated)

        # Wire table selection to display controller highlight
        self.roiManagerWidget.sigSelectionChanged.connect(
            self.roiDisplayController.highlightROI
        )

    def _onToolActivated(self, tool) -> None:
        """Connect drawing tool signals when a drawing tool is activated."""
        from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
            ROIDrawingTool,
        )

        if isinstance(tool, ROIDrawingTool):
            tool.sigROIDrawingComplete.connect(self._onROIDrawn)

    def _onROIDrawn(self, result: dict) -> None:
        """Handle completion of an ROI drawing tool."""
        self.roiCollection.addROIFromDrawing(
            geometry=result["geometry"],
            roiType=result["roiType"],
        )

    def setStatusMessage(self, message):
        """Set a status message in the status bar"""
        self.statusBar().showMessage(message)

    def closeEvent(self, event):
        """Handle workflow closure"""
        self.roiDisplayController.cleanup()
        self.workflowClosed.emit()  # Emit signal before closing
        super().closeEvent(event)
