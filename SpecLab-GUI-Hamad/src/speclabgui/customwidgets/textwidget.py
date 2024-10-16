from PyQt6 import QtCore, QtGui, QtWidgets


class TextWidget(QtWidgets.QWidget):
    def __init__(self, text: str):
        super(TextWidget, self).__init__()
        self.label = QtWidgets.QLabel(text)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.label)
