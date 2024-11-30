from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFormLayout, QLineEdit, QLabel
from PyQt6.QtCore import Qt, QModelIndex
from src.models.listmodel import ListModel


class EditableListView(QWidget):
    def __init__(self, model: ListModel, parent=None):
        super().__init__(parent)
        self.model = model
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.formLayout = QFormLayout()
        self.layout.addLayout(self.formLayout)
        self.setLayout(self.layout)
        self.populateForm()

    def populateForm(self):
        for row in range(self.model.rowCount()):
            index = self.model.index(row, 0)
            item = self.model.data(index, Qt.ItemDataRole.DisplayRole)
            if item:
                self.addFormRow(item, index)

    def addFormRow(self, item, index):
        name = item[0]
        values = item[1:]

        nameLabel = QLabel(name)
        self.formLayout.addRow(nameLabel)

        for i, value in enumerate(values):
            lineEdit = QLineEdit(str(value))
            lineEdit.editingFinished.connect(lambda idx=index, le=lineEdit, i=i: self.updateModel(idx, le, i))
            self.formLayout.addRow(f"Value {i+1}:", lineEdit)

    def updateModel(self, index, lineEdit, valueIndex):
        item = list(self.model.data(index, Qt.ItemDataRole.DisplayRole))
        item[valueIndex + 1] = lineEdit.text()
        self.model.setData(index, tuple(item), Qt.ItemDataRole.EditRole)
