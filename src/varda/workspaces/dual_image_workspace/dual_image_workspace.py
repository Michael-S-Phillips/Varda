# standard library
import logging
from enum import Enum

# third party imports
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
import pyqtgraph as pg

# local imports
from varda.common.parameter import (
    ImageParameter,
    ParameterGroup,
    EnumParameter,
)
from varda.common.entities import VardaRaster
from varda.image_rendering.raster_view import ImageViewport, ROIDisplayController
from varda.image_rendering.image_renderer import ImageRenderer
from varda.common.ui import (
    VBoxBuilder,
    SplitterBuilder,
    HBoxBuilder,
    VerticalScrollArea,
)
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget
from varda.plotting.plot import VardaPlotWidget

logger = logging.getLogger(__name__)


class DisplayMode(Enum):
    SIDE_BY_SIDE = 1
    OVERLAY = 2


class LinkMode(Enum):
    PIXEL = 1
    GEO = 2


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


class DualImageWorkspace(QWidget):
    def __init__(self, config: DualImageWorkspaceConfig, parent=None):
        super().__init__(parent)
        self.image1 = config.image1Param.get()
        self.image2 = config.image2Param.get()
        self.displayMode = config.displayModeParam.get()

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

    def _initSideBySide(self):
        self.viewport1 = ImageViewport(self.primaryRenderer, self)
        self.viewport2 = ImageViewport(self.secondaryRenderer, self)

        self.toolManager1 = ToolManager(self.viewport1, self)
        self.toolManager2 = ToolManager(self.viewport2, self)
        self.viewport1.addToolBar(self.toolManager1.getToolbar())
        self.viewport2.addToolBar(self.toolManager2.getToolbar())

        self.roiDisplayController.registerViewport("primary", self.viewport1)
        self.roiDisplayController.registerViewport("secondary", self.viewport2)

        # Only right viewport drawing tools create ROIs
        self._drawingToolManagers = [self.toolManager2]

        self.setLayout(
            HBoxBuilder().withWidget(
                SplitterBuilder(Qt.Orientation.Vertical)
                .withWidget(
                    SplitterBuilder(Qt.Orientation.Horizontal)
                    .withWidget(
                        SplitterBuilder(Qt.Orientation.Vertical)
                        .withWidget(self.viewport1, stretchFactor=2)
                        .withWidget(self.primaryRenderer.getSettingsPanel())
                    )
                    .withWidget(
                        SplitterBuilder(Qt.Orientation.Vertical)
                        .withWidget(self.viewport2, stretchFactor=2)
                        .withWidget(self.secondaryRenderer.getSettingsPanel())
                    ),
                    stretchFactor=3,
                )
                .withWidget(
                    SplitterBuilder(Qt.Orientation.Horizontal)
                    .withWidget(self.roiManagerWidget, stretchFactor=1)
                    .withWidget(self.plotWidget, stretchFactor=2),
                    stretchFactor=1,
                )
            )
        )

    def _initOverlay(self):
        self.viewport1 = ImageViewport(self.primaryRenderer, self)
        self.viewport1.overlayImage(self.secondaryRenderer)

        self.toolManager1 = ToolManager(self.viewport1, self)
        self.viewport1.addToolBar(self.toolManager1.getToolbar())

        self.roiDisplayController.registerViewport("overlay", self.viewport1)

        self._drawingToolManagers = [self.toolManager1]

        self.setLayout(
            HBoxBuilder().withWidget(
                SplitterBuilder(Qt.Orientation.Vertical)
                .withLayout(
                    VBoxBuilder()
                    .withWidget(self.viewport1)
                    .withLayout(
                        HBoxBuilder()
                        .withWidget(self.primaryRenderer.getSettingsPanel())
                        .withWidget(self.secondaryRenderer.getSettingsPanel())
                    ),
                    stretchFactor=3,
                )
                .withLayout(
                    HBoxBuilder()
                    .withWidget(self.roiManagerWidget, stretch=1)
                    .withWidget(self.plotWidget, stretch=2),
                    stretchFactor=1,
                )
            )
        )

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
