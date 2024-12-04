import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal


class ImageBasicStretchEditor(QWidget):
    def __init__(self, imageModel, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Stretch Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.imageModel = imageModel

        layout = QVBoxLayout()

        self.rLabel = QLabel("Red min/max")
        self.rMinInput = QLineEdit("0")
        self.rMinInput.editingFinished.connect(self.updateModel)
        self.rMaxInput = QLineEdit("1")
        self.rMaxInput.editingFinished.connect(self.updateModel)

        self.rLayout = QHBoxLayout()
        self.rLayout.addWidget(self.rLabel)
        self.rLayout.addWidget(self.rMinInput)
        self.rLayout.addWidget(self.rMaxInput)


        self.gLabel = QLabel("Green min/max")
        self.gMinInput = QLineEdit("0")
        self.gMinInput.editingFinished.connect(self.updateModel)
        self.gMaxInput = QLineEdit("1")
        self.gMaxInput.editingFinished.connect(self.updateModel)

        self.gLayout = QHBoxLayout()
        self.gLayout.addWidget(self.gLabel)
        self.gLayout.addWidget(self.gMinInput)
        self.gLayout.addWidget(self.gMaxInput)


        self.bLabel = QLabel("Blue min/max")
        self.bMinInput = QLineEdit("0")
        self.bMinInput.editingFinished.connect(self.updateModel)
        self.bMaxInput = QLineEdit("1")
        self.bMaxInput.editingFinished.connect(self.updateModel)

        self.bLayout = QHBoxLayout()
        self.bLayout.addWidget(self.bLabel)
        self.bLayout.addWidget(self.bMinInput)
        self.bLayout.addWidget(self.bMaxInput)


        layout.addLayout(self.rLayout)
        layout.addLayout(self.gLayout)
        layout.addLayout(self.bLayout)
        self.setLayout(layout)

        self.imageModel.stretchChanged.connect(self.updateView)
        
        self.show()

    def updateModel(self):
        self.imageModel.stretch = [[float(self.rMinInput.text()), float(self.rMaxInput.text())],
                                   [float(self.gMinInput.text()), float(self.gMaxInput.text())],
                                   [float(self.bMinInput.text()), float(self.bMaxInput.text())]]

    def updateView(self):
        levels = self.imageModel.stretch
        self.rMinInput.setText(str(levels[0][0]))
        self.rMaxInput.setText(str(levels[0][1]))
        self.gMinInput.setText(str(levels[1][0]))
        self.gMaxInput.setText(str(levels[1][1]))
        self.bMinInput.setText(str(levels[2][0]))
        self.bMaxInput.setText(str(levels[2][1]))
