from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QDialog


class ProcessDialog(QDialog):
    """Dialog box that can dynamically generate parameter controls for an image
    process.
    """

    sigProcessFinished = QtCore.pyqtSignal()

    def __init__(self, image=None):
        super().__init__()
        self.image = image

    def openProcessControlMenu(self, process):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle(process.name)
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(10)
        dialog.setLayout(layout)

        for name, details in process.parameters.items():
            paramName = QtWidgets.QLabel()
            paramName.setText(name)
            paramName.setToolTip(details["description"])

            if details["type"] == float:
                lineEdit = QtWidgets.QLineEdit()
                lineEdit.setText(str(details["default"]))
                lineEdit.setValidator(QtGui.QDoubleValidator())
                layout.addRow(paramName, lineEdit)
            elif details["type"] == bool:
                lineEdit = QtWidgets.QCheckBox()
                lineEdit.setChecked(details["default"])
                layout.addRow(paramName, lineEdit)

        layout.addItem(
            QtWidgets.QSpacerItem(
                0,
                20,
                QtWidgets.QSizePolicy.Policy.Minimum,
                QtWidgets.QSizePolicy.Policy.Expanding,
            )
        )
        executeButton = QtWidgets.QPushButton("Execute")
        executeButton.clicked.connect(lambda: self.processImage(process))
        layout.addWidget(executeButton)
        layout.addItem(
            QtWidgets.QSpacerItem(
                60,
                0,
                QtWidgets.QSizePolicy.Policy.Fixed,
                QtWidgets.QSizePolicy.Policy.Minimum,
            )
        )
        dialog.exec()

    def processImage(self, process):
        if self.image is None:
            return
        p = process()
        core.utilities.threading_helper.dispatchThreadProcess(
            self.image.process, self.sigProcessFinished, p
        )
