from PyQt6.QtWidgets import QDialog, QVBoxLayout, QPushButton
from varda.common.parameter import ImageParameter, ParameterGroup


class NewWorkspaceDialog(QDialog):
    def __init__(self, imageList, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Workspace")
        self.dualImageWorkspaceConfig = NewDualImageWorkspaceConfig(imageList)
        params = self.dualImageWorkspaceConfig.getParameters()
        layout = QVBoxLayout()
        layout.addWidget(params)

        self.finishButton = QPushButton("Finish")
        self.finishButton.clicked.connect(self.accept)
        self.finishButton.setDefault(True)
        layout.addWidget(self.finishButton)
        self.setLayout(layout)


class NewDualImageWorkspaceConfig:
    image1Param: ImageParameter
    image2Param: ImageParameter

    def __init__(self, imageList) -> None:
        self.image1Param: ImageParameter = ImageParameter("Primary Image", imageList)
        self.image2Param: ImageParameter = ImageParameter("Secondary Image", imageList)

    def getParameters(self):
        return ParameterGroup([self.image1Param, self.image2Param])
