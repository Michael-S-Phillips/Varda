# standard library
from enum import Enum
from typing import override

# third party imports
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt

# local imports
from varda.common.parameter import (
    ImageParameter,
    ParameterGroup,
    ParameterGroupWidget,
    EnumParameter,
)
from varda.common.entities import VardaRaster
from varda.image_rendering.raster_view import ImageViewport
from varda.image_rendering.image_renderer import ImageRenderer
from varda.common.ui import VBoxBuilder, SplitterBuilder, HBoxBuilder
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager


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

        # Init UI
        self.primaryRenderer = ImageRenderer(image=self.image1)
        self.secondaryRenderer = ImageRenderer(image=self.image2)

        if config.displayModeParam.get() == DisplayMode.SIDE_BY_SIDE:
            self.setLayout(self._sideBySideLayout())
        elif config.displayModeParam.get() == DisplayMode.OVERLAY:
            self.setLayout(self._overlayLayout())

    def _sideBySideLayout(self):
        self.viewport1 = ImageViewport(self.primaryRenderer, self)
        self.viewport2 = ImageViewport(self.secondaryRenderer, self)

        self.toolManager1 = ToolManager(self.viewport1, self)
        self.toolManager2 = ToolManager(self.viewport2, self)

        self.viewport1.addToolBar(self.toolManager1.getToolbar())
        self.viewport2.addToolBar(self.toolManager2.getToolbar())
        return HBoxBuilder().withWidget(
            SplitterBuilder(Qt.Orientation.Horizontal)
            .withLayout(
                VBoxBuilder()
                .withWidget(self.viewport1, stretch=2)
                .withWidget(self.primaryRenderer.getSettingsPanel(), 1)
            )
            .withLayout(
                VBoxBuilder()
                .withWidget(self.viewport2, stretch=2)
                .withWidget(self.secondaryRenderer.getSettingsPanel(), 1)
            )
        )

    def _overlayLayout(self):
        viewport = ImageViewport(self.primaryRenderer, self)
        viewport.overlayImage(self.secondaryRenderer)
        return (
            VBoxBuilder()
            .withWidget(viewport)
            .withLayout(
                HBoxBuilder()
                .withWidget(self.primaryRenderer.getSettingsPanel())
                .withWidget(self.secondaryRenderer.getSettingsPanel())
            )
        )


class OverlayDualImageWorkspace(QWidget):
    def __init__(self, config: DualImageWorkspaceConfig, parent=None):
        super().__init__(parent)
        self.image1 = config.image1Param.get()
        self.image2 = config.image2Param.get()

        self.primaryRenderer = ImageRenderer(self.image1)
        self.secondaryRenderer = ImageRenderer(self.image2)
        self.primarySettings = self.primaryRenderer.getSettingsPanel()
        self.secondarySettings = self.secondaryRenderer.getSettingsPanel()

        self.primaryViewport = ImageViewport(self.primaryRenderer, self)
        self.primaryViewport.overlayImage(self.secondaryRenderer)

        self.setLayout(
            VBoxBuilder()
            .withWidget(self.primaryViewport)
            .withLayout(
                HBoxBuilder()
                .withWidget(self.primarySettings)
                .withWidget(self.secondarySettings)
            )
        )


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
