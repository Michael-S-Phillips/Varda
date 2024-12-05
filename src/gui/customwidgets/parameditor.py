from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
                             QLabel)
from models.parametermodel import ParameterModel


class ParamEditor(QWidget):
    def __init__(self, paramModel, parent=None):
        super().__init__(parent)
        self.paramModel = paramModel
        self.initUI()

    def initUI(self):
        self.layout = QVBoxLayout(self)
        self.formLayout = QFormLayout()
        self.layout.addLayout(self.formLayout)

        self.populateForm()

        self.setLayout(self.layout)

    def populateForm(self):
        for param in self.paramModel:
            self.formLayout.addRow(QLabel(param.name))

            paramEditingLayout = QHBoxLayout()
            for key, value in param.values.items():
                paramName = QLabel(key)
                paramEdit = QLineEdit(value)
                paramEdit.editingFinished.connect(lambda p=param, k=key, le=paramEdit: self.updateModel(p, k, le))
                paramEditingLayout.addWidget(paramName)
                paramEditingLayout.addWidget(paramEdit)

            self.formLayout.addRow(paramEditingLayout)

    def updateModel(self, param, key, lineEdit):
        param.values[key] = lineEdit.text()
