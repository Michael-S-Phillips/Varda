"""Pick the image for a new spectral hourglass workspace."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QLabel

from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter, ParameterGroup
from varda.common.ui import ButtonBuilder, HBoxBuilder, VBoxBuilder
from varda.workspaces.spectral_hourglass.hourglass_workspace import (
    SpectralHourglassWorkspace,
)


class _Config(ParameterGroup):
    image = ImageParameter("Image", "The reflectance image to analyse.")

    def __init__(self, images: list[VardaRaster]) -> None:
        super().__init__()
        self.images = images
        self.image.setProvider(lambda: self.images)


class NewSpectralHourglassDialog(QDialog):
    sigCreateWorkspace = pyqtSignal(object)

    def __init__(self, images, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Spectral Hourglass Workspace")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.images = images
        self.config = _Config(list(images))
        self.accepted.connect(self._create)
        intro = QLabel(
            "Find the scene's endmembers and map them: MNF → pixel purity → "
            "n-D visualizer → identify against a spectral library → map. "
            "Results join the project's images."
        )
        intro.setWordWrap(True)
        self.setLayout(
            VBoxBuilder()
            .withWidget(intro)
            .withWidget(self.config.createWidget())
            .withStretch()
            .withLayout(
                HBoxBuilder()
                .withWidget(ButtonBuilder("Open").onClick(self.accept))
                .withStretch()
                .withWidget(ButtonBuilder("Cancel").onClick(self.reject))
            )
        )

    def _create(self) -> None:
        image = self.config.image.value
        if image is not None:
            self.sigCreateWorkspace.emit(SpectralHourglassWorkspace(image, self.images))

    def connectOnAccept(self, callback):
        self.sigCreateWorkspace.connect(callback)
        return self
