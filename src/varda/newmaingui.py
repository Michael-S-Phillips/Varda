from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMainWindow


class VardaMainWindow(QMainWindow):
    def __init__(self, menuBar, statusBar):
        super().__init__()
        self.menuBar = menuBar
        self.statusBar = statusBar
        self._initUI()

    def _initUI(self):
        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("resources/logo.svg"))

        self.setMenuBar(self.menuBar)
        self.setStatusBar(self.statusBar)
