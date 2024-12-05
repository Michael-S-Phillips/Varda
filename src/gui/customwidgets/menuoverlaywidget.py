from typing import override

from PyQt6 import QtWidgets, QtCore, QtGui


class MenuOverlayWidget(QtWidgets.QWidget):
    """
    A widget that displays a menu overlay on top of the main window.
    """

    def __init__(self, parent=None):
        super(MenuOverlayWidget, self).__init__(parent)

        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint |
                            QtCore.Qt.WindowType.WindowStaysOnTopHint)
        # self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TintedBackground)

        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        overlayLayout = QtWidgets.QVBoxLayout()
        button1 = QtWidgets.QPushButton("Button 1")
        button2 = QtWidgets.QPushButton("Button 2")
        overlayLayout.addWidget(button1)
        overlayLayout.addWidget(button2)
        self.setLayout(overlayLayout)

    @override
    def show(self):
        parentGeometry = self.parent().geometry()
        width = 200
        height = 200
        # self.setGeometry(parentGeometry)
        self.setGeometry(
            parentGeometry.topRight().x(),
            parentGeometry.topRight().y(),
            parentGeometry.width() // 4, parentGeometry.height() // 4)
        super().show()
