from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QLineEdit,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
)


class FilePathBox(QWidget):

    def __init__(self, defaultPath="", fileFilter=None, parent=None):
        super().__init__()
        self.fileFilter = fileFilter
        self.result = None
        self.filePathText = None
        self.openFileSelectorButton = None
        self._initUI(defaultPath)
        self._connectSignals()

    def _initUI(self, defaultPath):
        self.filePathText = QLineEdit(defaultPath)
        self.openFileSelectorButton = QPushButton("Browse Files...")
        layout = QHBoxLayout()
        layout.addWidget(self.filePathText)
        layout.addWidget(self.openFileSelectorButton)
        self.setLayout(layout)

    def _connectSignals(self):
        self.openFileSelectorButton.clicked.connect(self.getFilePath)
        self.filePathText.textChanged.connect(self.onTextChanged)

    def getFilePath(self):
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image File",
            "",
            self.fileFilter,
        )
        if filename:
            self.filePathText.setText(filename)

    def onTextChanged(self):
        self.result = self.filePathText.text()
