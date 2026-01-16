from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QMessageBox

from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisWorkflow,
    GeneralImageAnalysisConfig,
)
from varda.common.ui import VBoxBuilder, HBoxBuilder, ButtonBuilder


class NewGeneralImageAnalysisWorkspaceDialog(QDialog):
    sigCreateWorkspace = pyqtSignal(object)

    def __init__(self, imageList, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New General Image Analysis Workspace")
        if len(imageList) == 0:
            QMessageBox.warning(
                self, "No Images", "No images available to create a workspace."
            )
            self.reject()
            return
        self.config = GeneralImageAnalysisConfig(imageList)
        self.accepted.connect(
            lambda: self.sigCreateWorkspace.emit(
                GeneralImageAnalysisWorkflow(self.config)
            )
        )

        self.setLayout(
            VBoxBuilder()
            .withWidget(self.config.createWidget())
            .withStretch()
            .withLayout(
                HBoxBuilder()
                .withWidget(ButtonBuilder("Finish").onClick(self.accept))
                .withStretch()
                .withWidget(ButtonBuilder("Cancel").onClick(self.reject))
            )
        )

    def connectOnAccept(self, callback):
        self.sigCreateWorkspace.connect(callback)
        return self
