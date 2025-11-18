from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout
from PyQt6.QtCore import pyqtSignal
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    NewDualImageWorkspaceConfig,
    DualImageWorkspace,
)
from varda import log


class NewDualImageWorkspaceDialog(QDialog):
    sigCreateWorkspace = pyqtSignal(object)

    def __init__(self, imageList, parent=None):
        super().__init__(parent)
        log.debug("Initializing New Dual Image Workspace Dialog")

        self.setWindowTitle("Create New Dual Image Workspace")
        self.dualImageWorkspaceConfig = NewDualImageWorkspaceConfig(imageList)
        params = self.dualImageWorkspaceConfig.getParameters()
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(params)

        mainLayout.addStretch()

        buttonLayout = QHBoxLayout()
        self.finishButton = QPushButton("Finish")
        self.finishButton.clicked.connect(self.accept)
        self.finishButton.setDefault(True)
        buttonLayout.addWidget(self.finishButton)

        buttonLayout.addStretch()

        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)
        buttonLayout.addWidget(self.cancelButton)

        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

        self.accepted.connect(
            lambda: self.sigCreateWorkspace.emit(
                DualImageWorkspace(self.dualImageWorkspaceConfig)
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
    dialog.show()
    sys.exit(app.exec())
