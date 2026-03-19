# standard library
import logging
from enum import Enum

# third party imports
from PyQt6.QtWidgets import QMainWindow
import PyQt6Ads as ads

# local imports
from varda.common.parameter import (
    ImageParameter,
    ParameterGroup,
    EnumParameter,
)
from varda.common.entities import VardaRaster
from varda.image_rendering.raster_view import (
    ImageViewport,
    ROIDisplayController,
    ViewportLinkController,
    LinkMode,
)
from varda.image_rendering.image_renderer import ImageRenderer
from varda.common.ui import VardaDockWidget
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget
from varda.plotting.plot import VardaPlotWidget

logger = logging.getLogger(__name__)


class DisplayMode(Enum):
    SIDE_BY_SIDE = 1
    OVERLAY = 2


class DualImageWorkspaceConfig(ParameterGroup):
    imageList: list[VardaRaster]

    image1Param: ImageParameter = ImageParameter(
        "Primary Image",
        "Primary Image for Workspace (Usually a Spectral Image)",
    )
    image2Param: ImageParameter = ImageParameter(
        "Secondary Image",
        "Secondary Image for Workspace (Usually a Band Parameter Image)",
    )
    displayModeParam: EnumParameter = EnumParameter(
        "Display Mode",
        DisplayMode,
        DisplayMode.SIDE_BY_SIDE,
        "Display Mode for Dual Image Workspace",
    )
    linkModeParam: EnumParameter = EnumParameter(
        "Sync Mode",
        LinkMode,
        LinkMode.PIXEL,
        "Whether to link the images by pixel or geographic coordinates.",
    )

    def __init__(self, imageList: list[VardaRaster]) -> None:
        super().__init__()
        self.imageList = imageList
        self.image1Param.setProvider(lambda: self.imageList)
        self.image2Param.setProvider(lambda: self.imageList)


class DualImageWorkspace(QMainWindow):
    def __init__(self, config: DualImageWorkspaceConfig, parent=None):
        super().__init__(parent)
        self.image1 = config.image1Param.get()
        self.image2 = config.image2Param.get()
        self.displayMode = config.displayModeParam.get()
        self.linkMode = config.linkModeParam.get()

        self.viewportLinkController = None

        self._initComponents()
        self._initUI()
        self._connectSignals()

    def _initComponents(self):
        self.primaryRenderer = ImageRenderer(image=self.image1)
        self.secondaryRenderer = ImageRenderer(image=self.image2)

        # ROI system — collection uses secondary image's CRS/transform
        # (both images assumed to share the same transform)
        self.roiCollection = ROICollection.fromImage(self.image2)
        self.roiDisplayController = ROIDisplayController(
            self.roiCollection, self.image2, parent=self
        )
        self.roiManagerWidget = ROIManagerWidget(self.roiCollection, parent=self)
        self.plotWidget = VardaPlotWidget(parent=self)

    def _initUI(self):
        if self.displayMode == DisplayMode.SIDE_BY_SIDE:
            self._initSideBySide()
        elif self.displayMode == DisplayMode.OVERLAY:
            self._initOverlay()

    def _setupDocks(self):
        self.dockManager = ads.CDockManager(self)
        self.dockManager.setAutoHideConfigFlags(
            ads.CDockManager.eAutoHideFlag.DefaultAutoHideConfig
        )

        self.roiDock = VardaDockWidget("ROI Manager")
        self.roiDock.setWidget(self.roiManagerWidget)

        self.plotDock = VardaDockWidget("ROI Plots")
        self.plotDock.setWidget(self.plotWidget)

        self.primarySettingsDock = VardaDockWidget("Primary Render Settings")
        self.primarySettingsDock.setWidget(self.primaryRenderer.getSettingsPanel())

        self.secondarySettingsDock = VardaDockWidget("Secondary Render Settings")
        self.secondarySettingsDock.setWidget(self.secondaryRenderer.getSettingsPanel())

    def _initSideBySide(self):
        self.viewport1 = ImageViewport(
            self.primaryRenderer, mouseEnabled=True, parent=self
        )
        self.viewport2 = ImageViewport(
            self.secondaryRenderer, mouseEnabled=True, parent=self
        )

        self.toolManager1 = ToolManager(self.viewport1, self)
        self.toolManager2 = ToolManager(self.viewport2, self)
        self.viewport1.addToolBar(self.toolManager1.getToolbar())
        self.viewport2.addToolBar(self.toolManager2.getToolbar())

        self.roiDisplayController.registerViewport("primary", self.viewport1)
        self.roiDisplayController.registerViewport("secondary", self.viewport2)

        self.viewportLinkController = ViewportLinkController(
            self.viewport1, self.viewport2, self.linkMode, parent=self
        )

        # Only right viewport drawing tools create ROIs
        self._drawingToolManagers = [self.toolManager2]

        self._setupDocks()

        self.viewport1Dock = VardaDockWidget("Primary Viewport")
        self.viewport1Dock.setWidget(self.viewport1)

        self.viewport2Dock = VardaDockWidget("Secondary Viewport")
        self.viewport2Dock.setWidget(self.viewport2)

        # Top row: two viewports side by side
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.CenterDockWidgetArea,
            self.viewport1Dock,
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea,
            self.viewport2Dock,
            self.viewport1Dock.dockAreaWidget(),
        )

        # Settings panels as auto-hide on the bottom sidebar
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea,
            self.primarySettingsDock,
            self.viewport1Dock.dockAreaWidget(),
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea,
            self.secondarySettingsDock,
            self.viewport2Dock.dockAreaWidget(),
        )

        # Bottom row: ROI manager and plot side by side
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea, self.roiDock
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea,
            self.plotDock,
            self.roiDock.dockAreaWidget(),
        )
        self.dockManager.setSplitterSizes(self.viewport1Dock.dockAreaWidget(), [4, 1])
        # Within each viewport column, give viewport more space than its settings
        viewport1Splitter = self.viewport1Dock.dockAreaWidget().parentSplitter()
        if viewport1Splitter:
            viewport1Splitter.setSizes([500, 150])
        viewport2Splitter = self.viewport2Dock.dockAreaWidget().parentSplitter()
        if viewport2Splitter:
            viewport2Splitter.setSizes([500, 150])

    def _initOverlay(self):
        self.viewport1 = ImageViewport(self.primaryRenderer, self)
        self.viewport1.overlayImage(self.secondaryRenderer)

        self.toolManager1 = ToolManager(self.viewport1, self)
        self.viewport1.addToolBar(self.toolManager1.getToolbar())

        self.roiDisplayController.registerViewport("overlay", self.viewport1)

        self._drawingToolManagers = [self.toolManager1]

        self._setupDocks()

        self.viewport1Dock = VardaDockWidget("Overlay Viewport")
        self.viewport1Dock.setWidget(self.viewport1)

        # Viewport as the main area
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.CenterDockWidgetArea, self.viewport1Dock
        )

        # Both settings panels as auto-hide on the bottom sidebar
        self.dockManager.addAutoHideDockWidget(
            ads.SideBarLocation.SideBarBottom, self.primarySettingsDock
        )
        self.dockManager.addAutoHideDockWidget(
            ads.SideBarLocation.SideBarBottom, self.secondarySettingsDock
        )

        # Bottom row: ROI manager and plot side by side
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea, self.roiDock
        )
        self.dockManager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea,
            self.plotDock,
            self.roiDock.dockAreaWidget(),
        )

        # Give viewport most vertical space, settings and ROI/plot less
        rootSplitter = self.dockManager.rootSplitter()
        rootSplitter.setSizes([600, 200])

    def _connectSignals(self):
        # Wire drawing tools (only right viewport in side-by-side, single viewport in overlay)
        for tm in self._drawingToolManagers:
            tm.sigToolActivated.connect(self._onToolActivated)

        # Wire table selection to highlight
        self.roiManagerWidget.sigSelectionChanged.connect(
            self.roiDisplayController.highlightROI
        )

        # Wire spectral plot
        self.roiManagerWidget.sigPlotRequested.connect(self._onPlotRequested)

    def _onToolActivated(self, tool) -> None:
        from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
            ROIDrawingTool,
        )

        if isinstance(tool, ROIDrawingTool):
            tool.sigROIDrawingComplete.connect(self._onROIDrawn)

    def _onROIDrawn(self, result: dict) -> None:
        self.roiCollection.addROIFromDrawing(
            geometry=result["geometry"],
            roiType=result["roiType"],
        )

    def _onPlotRequested(self, fid: int) -> None:
        """Plot mean spectrum using data from the primary (spectral) image."""
        stats = self.roiCollection.getROIStatistics(fid, self.image1)

        if stats["pixel_count"] == 0:
            logger.warning("ROI fid=%d has no pixels in primary image", fid)
            return

        mean = stats["mean"]
        wavelengths = VardaPlotWidget.getPlottableWavelengths(self.image1, len(mean))
        roi = self.roiCollection.getROI(fid)
        logger.debug(f"plot requested. mean data: {mean}")

        self.plotWidget.plot(
            wavelengths,
            mean,
            pen=roi.color,
            name=roi.name,
        )

    def closeEvent(self, event):
        if self.viewportLinkController is not None:
            self.viewportLinkController.cleanup()
        self.roiDisplayController.cleanup()
        super().closeEvent(event)


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from varda.utilities import debug

    app = QApplication(sys.argv)
    imageList = [
        debug.generate_random_image(),
        debug.generate_random_image(),
    ]
    config = DualImageWorkspaceConfig(imageList)
    workspace = DualImageWorkspace(config)
    workspace.setMaximumSize(1200, 800)
    workspace.show()
    sys.exit(app.exec())
