from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QCheckBox, QPushButton
from PyQt6.QtWidgets import QColorDialog


class ROIPropertyEditor(QWidget):
    def __init__(self, roiManager, parent=None):
        super().__init__(parent)
        self.roiManager = roiManager
        self.currentRoiId = None

        layout = QFormLayout(self)
        self.nameEdit = QLineEdit()
        layout.addRow("Name:", self.nameEdit)
        self.visibleCheck = QCheckBox()
        layout.addRow("Visible:", self.visibleCheck)
        self.colorBtn = QPushButton("Change…")
        layout.addRow("Color:", self.colorBtn)

        # Connect signals
        self.nameEdit.editingFinished.connect(self._onNameEdited)
        self.visibleCheck.toggled.connect(self._onVisibleToggled)
        self.colorBtn.clicked.connect(self._onChangeColor)

    def setRoi(self, roi):
        self.currentRoiId = roi.id if roi else None
        self.nameEdit.setText(roi.name if roi else "")
        self.visibleCheck.setChecked(roi.visible if roi else False)

    def _onNameEdited(self):
        name = self.nameEdit.text()
        self.roiManager.updateROI(self.currentRoiId, name=name)

    def _onVisibleToggled(self, checked):
        self.roiManager.updateROI(self.currentRoiId, visible=checked)

    def _onChangeColor(self):

        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.roiManager.updateROI(self.currentRoiId, color=color)
