from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6.QtCore import pyqtSignal
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspaceConfig,
    DualImageWorkspace,
)
from varda import log
from varda.common.ui import VBoxBuilder, HBoxBuilder, ButtonBuilder


class NewDualImageWorkspaceDialog(QDialog):
    sigCreateWorkspace = pyqtSignal(object)

    def __init__(self, imageList, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Dual Image Workspace")
        if len(imageList) == 0:
            QMessageBox.warning(
                self, "No Images", "No images available to create a workspace."
            )
            self.reject()
            return

        self.dualImageWorkspaceConfig = DualImageWorkspaceConfig(imageList)
        self.accepted.connect(
            lambda: self.sigCreateWorkspace.emit(
                DualImageWorkspace(self.dualImageWorkspaceConfig)
            )
        )

        self.setLayout(
            VBoxBuilder()
            .withWidget(self.dualImageWorkspaceConfig.createWidget())
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


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    from varda.utilities import debug

    app = QApplication(sys.argv)
    dialog = NewDualImageWorkspaceDialog([debug.generate_random_image()])
    dialog.connectOnAccept(lambda workspace: workspace.show())
    dialog.show()
    sys.exit(app.exec())
