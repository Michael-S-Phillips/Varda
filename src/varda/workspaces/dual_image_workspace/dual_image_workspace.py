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


class BetterVBoxLayout(QVBoxLayout):
    @override
    def addWidget(self, a0, stretch=0, alignment=Qt.AlignmentFlag(0)):
        super().addWidget(a0, stretch, alignment)
        return self


class WrapperWidget(QWidget):
    def __init__(self, layout, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)


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
        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(
            WrapperWidget(
                BetterVBoxLayout()
                .addWidget(self.primaryViewport, 2)
                .addWidget(self.primarySettings, 1)
            )
        )
        splitter.addWidget(
            WrapperWidget(
                BetterVBoxLayout()
                .addWidget(self.secondaryViewport, 2)
                .addWidget(self.secondarySettings)
            )
        )
        layout = QHBoxLayout()
        layout.addWidget(splitter)
        self.setLayout(layout)


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
