# src/speclabgui/maingui.py

from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg
from speclabgui.customwidgets import SpectralImageWorkspace, FileExplorer
from speclabgui.customwidgets.controlPanel import ControlPanel  # Import ControlPanel
import sys

class MainGui(QtWidgets.QMainWindow):
    """
    Creates the main window and layout for the GUI.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SpecLab")
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.initUI()

    def initUI(self):
        # Create a splitter for the main layout
        splitter = QtWidgets.QSplitter()

        # File Explorer as a dockable widget
        self.fileExplorerDock = QtWidgets.QDockWidget("File Explorer", self)
        self.fileExplorer = FileExplorer()
        self.fileExplorerDock.setWidget(self.fileExplorer)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, self.fileExplorerDock)

        # Control Panel as a dockable widget
        self.controlPanelDock = QtWidgets.QDockWidget("Control Panel", self)
        self.controlPanel = ControlPanel()
        self.controlPanelDock.setWidget(self.controlPanel)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.controlPanelDock)

        # Spectral Image Workspace as a dockable widget
        self.imageViewDock = QtWidgets.QDockWidget("Image Workspace", self)
        self.imageView = SpectralImageWorkspace(self)
        self.imageViewDock.setWidget(self.imageView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea, self.imageViewDock)

        # Setup the menu bar
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('File')
        fileMenu.addAction('Open', self.openFile)
        fileMenu.addAction('Save', self.saveFile)
        fileMenu.addAction('Exit', self.exitApp)

        helpMenu = menuBar.addMenu('Help')
        helpMenu.addAction('About', self.aboutDialog)

        # Create a central widget
        widget = QtWidgets.QWidget()
        splitter.addWidget(self.imageView)
        widget.setLayout(QtWidgets.QVBoxLayout())
        widget.layout().addWidget(splitter)
        self.setCentralWidget(widget)

    def openFile(self):
        print("Open file dialog...")

    def saveFile(self):
        print("Save file functionality...")

    def exitApp(self):
        self.close()

    def aboutDialog(self):
        print("Show about dialog...")


def startGui():
    app = QtWidgets.QApplication(sys.argv)
    window = MainGui()
    window.showMaximized()
    window.show()
    app.exec()


if __name__ == "__main__":
    startGui()
