"""
This module contains the ImageBasicStretchEditor class,
which is a custom widget that allows the user to edit the stretch.
"""

# standard library

# third party imports
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QLineEdit, QHBoxLayout, QSpinBox
from PyQt6.QtCore import Qt

# local imports
from gui.views.baseimageview import BaseImageView


class ImageViewStretchEditor(BaseImageView):

    def __init__(self, imageModel, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rLabel: QLabel | None = None
        self.rMinInput: QLineEdit | None = None
        self.rMaxInput: QLineEdit | None = None

        self.gLabel: QLabel | None = None
        self.gMinInput: QLineEdit | None = None
        self.gMaxInput: QLineEdit | None = None

        self.bLabel: QLabel | None = None
        self.bMinInput: QLineEdit | None = None

        self.initUI()
        self.setImageModel(imageModel)
        self.show()

    def initUI(self):
        self.setWindowTitle("Stretch Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

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

        self.setViewLayout(layout)

    def setImageModel(self, image):
        super().setImageModel(image)
        self.onStretchChanged()

    def updateModel(self):
        self.setStretchValues(float(self.rMinInput.text()), float(self.rMaxInput.text()),
                              float(self.gMinInput.text()), float(self.gMaxInput.text()),
                              float(self.bMinInput.text()), float(self.bMaxInput.text())
                              )

    def onStretchChanged(self):
        levels = self.getStretch().values
        self.rMinInput.setText(str(levels[0][0]))
        self.rMaxInput.setText(str(levels[0][1]))
        self.gMinInput.setText(str(levels[1][0]))
        self.gMaxInput.setText(str(levels[1][1]))
        self.bMinInput.setText(str(levels[2][0]))
        self.bMaxInput.setText(str(levels[2][1]))
