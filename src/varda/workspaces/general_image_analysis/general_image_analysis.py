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

from varda.common.entities import VardaRaster
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import (
    NewHistogramView,
)
import PyQt6Ads as ads


from varda.image_rendering.raster_view import TripleRasterView, ROIDisplayController
from varda.image_rendering.raster_view.viewport_context_menu_controller import (
    ViewportContextMenuController,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool_controller import (
    ViewportToolController,
)
from varda.common.parameter import ImageParameter, ParameterGroup
from varda.plotting.plot import VardaPlotWidget
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget
from varda.common.ui import VardaDockWidget

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

        # One shared toolbar drives a tool across all three viewports.
        self.toolController = ViewportToolController(
            [
                self.tripleRasterView.viewport1,
                self.tripleRasterView.viewport2,
                self.tripleRasterView.viewport3,
            ],
            self,
        )
        self.addToolBar(self.toolController.toolBar)

        # initialize histogram view
        self.histogram = NewHistogramView(self.imageRenderer, self)

        # --- ROI system ---
        image = self.config.image.value
        self.roiCollection = ROICollection.fromImage(image)

        self.roiDisplayController = ROIDisplayController(
            self.roiCollection, parent=self
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

        # --- Spectral plot ---
        self.plotWidget = VardaPlotWidget(parent=self)

        self.roiManagerWidget = ROIManagerWidget(
            self.roiCollection, image, self.plotWidget, parent=self
        )

        # --- Viewport context menu (place template) ---
        self.viewportContextMenuController = ViewportContextMenuController(
            self.roiManagerWidget, parent=self
        )
        for vp in (
            self.tripleRasterView.viewport1,
            self.tripleRasterView.viewport2,
            self.tripleRasterView.viewport3,
        ):
            vp.sigContextMenuRequested.connect(
                self.viewportContextMenuController.onContextMenuRequested
            )

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

        self.dockManager = ads.CDockManager(self)

        # dockArea = DockArea(self)
        # self.setCentralWidget(dockArea)
        # docks = []

        self.rasterDock = VardaDockWidget("Raster Dock")
        # self.rasterDock.setFeature(
        #     ads.CDockWidget.DockWidgetFeature.DockWidgetClosable, False
        # )
        self.rasterDock.setWidget(self.tripleRasterView)

        # rasterDock = Dock("Raster Dock", widget=self.tripleRasterView, size=(800, 800))
        # docks.append(rasterDock)

        self.settingsDock = VardaDockWidget("Render Settings")
        self.settingsDock.setWidget(self.rendererSettingsPanel)

        # settingsDock = Dock(
        #     "Render Settings", widget=self.rendererSettingsPanel, size=(100, 100)
        # )
        # docks.append(settingsDock)

        self.roiDock = VardaDockWidget("ROI Manager")
        self.roiDock.setWidget(self.roiManagerWidget)

        # roiDockNew = Dock("ROI Dock", widget=self.roiManagerWidget, size=(100, 100))
        # docks.append(roiDockNew)

        self.histogramDock = VardaDockWidget("Histogram")
        self.histogramDock.setWidget(self.histogram)

        # histogramDock = Dock("Histogram Dock", widget=self.histogram)
        # docks.append(histogramDock)

        self.plotDock = VardaDockWidget("ROI Plots")
        self.plotDock.setWidget(self.plotWidget)

        self.dockManager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea, self.rasterDock
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.LeftDockWidgetArea,
            self.settingsDock,
            self.rasterDock.dockAreaWidget(),
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea,
            self.histogramDock,
            self.settingsDock.dockAreaWidget(),
        )

        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea, self.roiDock
        )

        self.dockManager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea,
            self.plotDock,
            self.roiDock.dockAreaWidget(),
        )

        # plotDock = Dock("Spectral Plot", widget=self.plotWidget, size=(400, 300))
        # docks.append(plotDock)

        # dockArea.addDock(rasterDock, "right")
        # dockArea.addDock(settingsDock, "left")
        # dockArea.addDock(roiDockNew, "bottom", settingsDock)
        # dockArea.addDock(histogramDock, "bottom", roiDockNew)
        # dockArea.addDock(plotDock, "bottom", rasterDock)

    def _connectSignals(self):
        """Connect signals between workflow components"""

        # Wire ROI drawing tools to the collection via the shared controller.
        self.toolController.sigToolActivated.connect(self._onToolActivated)

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
