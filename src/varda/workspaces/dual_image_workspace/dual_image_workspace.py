# standard library
from typing import override

# third party imports
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter
from PyQt6.QtCore import Qt

# local imports
from varda.common.parameter import ImageParameter, ParameterGroup
from varda.common.entities import Image
from varda.image_rendering.raster_view import ImageViewport
from varda.image_rendering.image_renderer import ImageRenderer
from varda.common.widgets import VBoxBuilder, SplitterBuilder, HBoxBuilder


class NewDualImageWorkspaceConfig:
    image1Param: ImageParameter
    image2Param: ImageParameter

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

    def getParameters(self):
        return ParameterGroup([self.image1Param, self.image2Param])


class DualImageWorkspace(QWidget):
    def __init__(self, config: NewDualImageWorkspaceConfig, parent=None):
        super().__init__(parent)
        self.image1 = config.image1Param.get()
        self.image2 = config.image2Param.get()

        # Init UI
        self.primaryRenderer = ImageRenderer(self.image1)
        self.secondaryRenderer = ImageRenderer(self.image2)
        self.primarySettings = self.primaryRenderer.getSettingsPanel()
        self.secondarySettings = self.secondaryRenderer.getSettingsPanel()

        self.primaryViewport = ImageViewport(self.primaryRenderer, self)
        self.secondaryViewport = ImageViewport(self.secondaryRenderer, self)

        splitter = (
            SplitterBuilder(Qt.Orientation.Horizontal)
            .withLayout(
                VBoxBuilder()
                .withWidget(self.primaryViewport, 2)
                .withWidget(self.primarySettings, 1)
            )
            .withLayout(
                VBoxBuilder()
                .withWidget(self.secondaryViewport, 2)
                .withWidget(self.secondarySettings, 1)
            )
        )

        self.setLayout(HBoxBuilder().withWidget(splitter))


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from varda.utilities import debug

    app = QApplication(sys.argv)
    imageList = [
        debug.generate_random_image(),
        debug.generate_random_image(),
    ]
    config = NewDualImageWorkspaceConfig(imageList)
    workspace = DualImageWorkspace(config)
    workspace.setMaximumSize(1200, 800)
    workspace.show()
    sys.exit(app.exec())
