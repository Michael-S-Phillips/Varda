"""
General Image Analysis Workflow

A comprehensive workflow for performing general image analysis with integrated
ROI drawing, band selection, stretch controls, and metadata management.
"""

import logging

from PyQt6.QtWidgets import QMainWindow, QStatusBar, QWidget
from pyqtgraph.dockarea import DockArea, Dock

from varda.common.entities import VardaRaster
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import (
    NewHistogramView,
)
import pyqtgraph as pg
import PyQt6Ads as ads


from varda.image_rendering.raster_view import TripleRasterView, ROIDisplayController
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
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

        # --- Spectral plot ---
        self.plotWidget = VardaPlotWidget(parent=self)

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

        # Wire ROI spectral plot
        self.roiManagerWidget.sigPlotRequested.connect(self._onPlotRequested)

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

    def _onPlotRequested(self, fid: int) -> None:
        """Compute ROI statistics and plot mean +/- std spectrum."""
        from PyQt6.QtGui import QColor

        image = self.config.image.value
        stats = self.roiCollection.getROIStatistics(fid, image)

        if stats["pixel_count"] == 0:
            logger.warning("ROI fid=%d has no pixels", fid)
            return

        mean = stats["mean"]
        std = stats["std"]
        wavelengths = VardaPlotWidget.getPlottableWavelengths(image, len(mean))

        roi = self.roiCollection.getROI(fid)

        fillColor = QColor(roi.color)
        fillColor.setAlpha(50)

        self.plotWidget.plot(wavelengths, mean, pen=roi.color, name=roi.name)
        # self.plotWidget.plotWithFill(
        #     wavelengths,
        #     mean,
        #     yLower=mean - std,
        #     yUpper=mean + std,
        #     fillBrush=pg.mkBrush(fillColor),
        #     pen=pg.mkPen(color=roi.color, width=2),
        #     name=roi.name,
        # )

    def setStatusMessage(self, message):
        """Set a status message in the status bar"""
        self.statusBar().showMessage(message)

    def closeEvent(self, event):
        """Handle workflow closure"""
        self.roiDisplayController.cleanup()
        self.workflowClosed.emit()  # Emit signal before closing
        super().closeEvent(event)
