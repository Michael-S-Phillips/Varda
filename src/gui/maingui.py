from gui import maingui

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from gui.customwidgets import FileExplorer, SpectralImageWorkspace
from gui.customwidgets.controlpanel import ControlPanel
from pathlib import Path
from PyQt6.QtGui import QIcon
import sys
import os

'''
"FYI": maingui.py will initialize window and layout.
It will only interact with widget classes (in customwidgets) to maintain
low cohesion. Widget classes will interact with processing / 
visualization classes accordingly. 
'''


class MainGui(QtWidgets.QMainWindow):
    """
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Varda")
        # set configs
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.initUI()

    def initUI(self):
        # Create a splitter for the main layout
        splitter = QtWidgets.QSplitter()

        # File Explorer as a dockable workspaceTabs
        self.fileExplorerDock = QtWidgets.QDockWidget("File Explorer", self)
        self.fileExplorer = FileExplorer()
        self.fileExplorerDock.setWidget(self.fileExplorer)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.fileExplorerDock)

        # Tabs as a dockable workspaceTabs
        self.controlPanel = ControlPanel(self)
        # self.tabsDock = QtWidgets.QDockWidget("Tabs", self)
        # tabWidget = QtWidgets.QTabWidget()
        # tabWidget.addTab(TextWidget("Controls and Actions"), "Control Panel")
        # tabWidget.addTab(TextWidget("Adjust Settings"), "Settings")
        # tabWidget.addTab(TextWidget("View Logs"), "Logs")
        # self.tabsDock.setWidget(tabWidget)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
                           self.controlPanel.tabsDock)

        # Spectral Image Workspace as a dockable workspaceTabs
        self.imageViewDock = QtWidgets.QDockWidget("Image Workspace", self)
        self.imageView = SpectralImageWorkspace(self)
        self.imageViewDock.setWidget(self.imageView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
                           self.imageViewDock)

        # Setup the menu bar
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('File')
        fileMenu.addAction('Open', self.openFile)
        fileMenu.addAction('Save', self.saveFile)
        fileMenu.addAction('Exit', self.exitApp)

        helpMenu = menuBar.addMenu('Help')
        helpMenu.addAction('About', self.aboutDialog)

        # Create a central workspaceTabs
        workspaceTabs = QtWidgets.QTabWidget()
        splitter.addWidget(self.imageView)
        workspaceTabs.setLayout(QtWidgets.QVBoxLayout())
        workspaceTabs.addTab(splitter, "workspace 1")
        self.setCentralWidget(workspaceTabs)

        self.setWindowIcon(QIcon("./img/logo.svg"))

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
    # Remove external stylesheet to revert to default Qt styling
    window = MainGui()
    window.showMaximized()
    window.show()
    app.exec()


if __name__ == "__main__":
    startGui()
