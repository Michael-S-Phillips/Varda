# standard library
from enum import Enum

# third party imports
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt

# local imports
from varda.common.parameter import ImageParameter, ParameterGroup, EnumParameter
from varda.common.entities import Image
from varda.image_rendering.raster_view import ImageViewport
from varda.image_rendering.image_renderer import ImageRenderer
from varda.common.widgets import VBoxBuilder, SplitterBuilder, HBoxBuilder


class DualImageWorkspaceConfig:
    image1Param: ImageParameter
    image2Param: ImageParameter
    displayModeParam: EnumParameter
    linkModeParam: EnumParameter

    class DisplayMode(Enum):
        SIDE_BY_SIDE = 1
        OVERLAY = 2

    class LinkMode(Enum):
        PIXEL = 1
        GEO = 2

    def __init__(self, imageList: list[Image]) -> None:
        self.image1Param: ImageParameter = ImageParameter(
            "Primary Image",
            imageList,
            "Primary Image for Workspace (Usually a Spectral Image)",
        )
        self.image2Param: ImageParameter = ImageParameter(
            "Secondary Image",
            imageList,
            "Secondary Image for Workspace (Usually a Band Parameter Image)",
        )
        self.displayModeParam: EnumParameter = EnumParameter(
            "Display Mode",
            self.DisplayMode,
            self.DisplayMode.SIDE_BY_SIDE,
            "Display Mode for Dual Image Workspace",
        )
        self.linkModeParam: EnumParameter = EnumParameter(
            "Sync Mode",
            self.LinkMode,
            self.LinkMode.PIXEL,
            "Whether to link the images by pixel or geographic coordinates.",
        )

    def getParameters(self):
        return ParameterGroup(
            [
                self.image1Param,
                self.image2Param,
                self.displayModeParam,
                self.linkModeParam,
            ]
        )


class DualImageWorkspace(QWidget):
    def __init__(self, config: DualImageWorkspaceConfig, parent=None):
        super().__init__(parent)
        self.image1 = config.image1Param.get()
        self.image2 = config.image2Param.get()

        # Init UI
        self.primaryRenderer = ImageRenderer(image=self.image1)
        self.secondaryRenderer = ImageRenderer(image=self.image2)

        if config.displayModeParam.get() == config.DisplayMode.SIDE_BY_SIDE:
            self.setLayout(self._sideBySideLayout())
        elif config.displayModeParam.get() == config.DisplayMode.OVERLAY:
            self.setLayout(self._overlayLayout())

    def _sideBySideLayout(self):
        return HBoxBuilder().withWidget(
            SplitterBuilder(Qt.Orientation.Horizontal)
            .withLayout(
                VBoxBuilder()
                .withWidget(ImageViewport(self.primaryRenderer, self), 2)
                .withWidget(self.primaryRenderer.getSettingsPanel(), 1)
            )
            .withLayout(
                VBoxBuilder()
                .withWidget(ImageViewport(self.secondaryRenderer, self), 2)
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
