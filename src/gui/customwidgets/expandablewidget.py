from PyQt6 import QtWidgets, QtCore, QtGui


class ExpandableWidget(QtWidgets.QWidget):
    """
    A widget that can be expanded and collapsed.
    """

    def __init__(self, parent=None):
        super(ExpandableWidget, self).__init__(parent)

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.menu = QtWidgets.QMenuBar()
        self.layout.setMenuBar(self.menu)
        self.menu.addAction("Collapse", self.collapse)

    def collapse(self):
        self.resize(QtCore.QSize(0, 0))
