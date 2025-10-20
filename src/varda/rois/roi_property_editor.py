from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QSlider,
)
from PyQt6.QtWidgets import QColorDialog

from varda.common.entities import ROI


class ROIPropertyEditor(QWidget):
    DEFAULT_OPACITY = 100

    def __init__(self, roiManager, parent=None):
        super().__init__(parent)
        self.roiManager = roiManager
        self.currentRoi: Optional[ROI] = None

        layout = QFormLayout(self)
        self.nameEdit = QLineEdit()
        layout.addRow("Name:", self.nameEdit)
        self.visibleCheck = QCheckBox()
        layout.addRow("Visible:", self.visibleCheck)
        self.colorBtn = QPushButton("Change…")
        layout.addRow("Color:", self.colorBtn)
        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(0, 255)  # 0-255 for alpha channel
        self.opacitySlider.setValue(self.DEFAULT_OPACITY)
        layout.addRow("Opacity:", self.opacitySlider)

        # Connect signals
        self.nameEdit.editingFinished.connect(self._onNameEdited)
        self.visibleCheck.toggled.connect(self._onVisibleToggled)
        self.colorBtn.clicked.connect(self._onChangeColor)
        self.opacitySlider.valueChanged.connect(self._onOpacityChanged)

    def setRoi(self, roi: ROI = None):
        self.currentRoi = roi
        self.nameEdit.setText(roi.name if roi else "(No ROI selected)")
        self.visibleCheck.setChecked(roi.visible if roi else False)
        self.opacitySlider.setValue(roi.color.alpha() if roi else self.DEFAULT_OPACITY)

    def _onNameEdited(self):
        name = self.nameEdit.text()
        self.roiManager.updateROI(self.currentRoi.id, name=name)

    def _onVisibleToggled(self, checked):
        self.roiManager.updateROI(self.currentRoi.id, visible=checked)

    def _onChangeColor(self):

        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            # maintain the alpha channel of the current ROI color
            newColor = QColor(
                color.red(), color.green(), color.blue(), self.currentRoi.color.alpha()
            )
            self.roiManager.updateROI(self.currentRoi.id, color=newColor)

    def _onOpacityChanged(self, value):
        if self.currentRoi:
            # Update the ROI color with the new opacity
            newColor = QColor(
                self.currentRoi.color.red(),
                self.currentRoi.color.green(),
                self.currentRoi.color.blue(),
                value,
            )
            self.roiManager.updateROI(self.currentRoi.id, color=newColor)
