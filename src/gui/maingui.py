# standard library
import datetime
from pathlib import Path
import logging
import sys
import os

# third party imports
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QIcon
import pyqtgraph as pg

# local imports
import vardathreading
from gui.customwidgets.controlpanel import ControlPanel
from models import ImageLoader
from models.imagemanager import ImageManager
from gui.customwidgets import (FileExplorer, ImageWorkspace, ExpandableWidget,
                               ImageListView)

'''
"FYI": maingui.py will initialize window and layout.
It will only interact with widget classes (in customwidgets) to maintain
low cohesion. Widget classes will interact with processing / 
visualization classes accordingly. 
'''
# Create a "logs" directory if it doesn't exist
logger = logging.getLogger(__name__)

class MainGUI(QtWidgets.QMainWindow):
    """
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Varda")
        # set pyqtgraph configs
        pg.setConfigOptions(imageAxisOrder='row-major')


        logger.info("Started")
        self.initUI()
        logger.info("UI Initialized")

    def initUI(self):
        # make dock tabs appear on top
        self.setTabPosition(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
                            QtWidgets.QTabWidget.TabPosition.North)

        self.imageListViewDock = QtWidgets.QDockWidget("Image List", self)
        self.imageListViewDock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)

        self.imageManager = ImageManager()
        self.imageListView = ImageListView(self, self.imageManager)
        self.imageListViewDock.setWidget(self.imageListView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea,
                           self.imageListViewDock)

        self.controlPanel = ControlPanel(None)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.RightDockWidgetArea,
                           self.controlPanel.tabsDock)

        # set default central widget
        label = QtWidgets.QLabel("Go to File->import to open your first image!")
        label.setStyleSheet("font-size: 20px;")
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)



        self.initMenuBar()

        # Create a central workspaceTabs
        self.setWindowIcon(QIcon("./img/logo.svg"))

    def initMenuBar(self):
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu('File')
        fileMenu.addAction('Open Project')
        recentMenu = fileMenu.addMenu('Open Recent')
        fileMenu.addAction('Save', self.saveFile)
        importMenu = fileMenu.addMenu('Import')
        importMenu.addAction('Import Image', self.openFile)
        fileMenu.addAction('Exit', self.exitApp)
        helpMenu = menuBar.addMenu('Help')
        helpMenu.addAction('About', self.aboutDialog)

    def initSplitter(self):
        """
        small test for adding buttons to expand/collapse side of splitter. doesn't
        work proper yet
        """
        splitter = QtWidgets.QSplitter(self)
        splitter.addWidget(QtWidgets.QTextEdit(self))
        splitter.addWidget(QtWidgets.QTextEdit(self))
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(splitter)
        handle = splitter.handle(1)
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        button = QtWidgets.QToolButton(handle)
        button.setArrowType(QtCore.Qt.ArrowType.LeftArrow)
        button.clicked.connect(
            lambda: self.handleSplitterButton(True))
        layout.addWidget(button)
        button = QtWidgets.QToolButton(handle)
        button.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        button.clicked.connect(
            lambda: self.handleSplitterButton(False))
        layout.addWidget(button)
        handle.setLayout(layout)

        return splitter

    def handleSplitterButton(self, left=True):
        if not all(self.splitter.sizes()):
            self.splitter.setSizes([1, 1])
        elif left:
            self.splitter.setSizes([0, 1])
        else:
            self.splitter.setSizes([1, 0])

    def openFile(self):
        # TODO: automatically determine all file types that are supported
        fileName = QtWidgets.QFileDialog.getOpenFileName(self,
                                                          "Open File", "",
                                                          "image file (*.hdr *.img "
                                                          "*.h5)")
        if fileName[0] is False:
            return
        vardathreading.dispatchThreadProcess(ImageLoader.new_image,
                                             self.onImageLoaded, fileName[0])

    def onImageLoaded(self, image):
        print("Image loaded:", image)
        self.imageManager.addImage(image)

        imageView = ImageWorkspace(self)
        imageView.setImageObject(image)
        # remove initial prompt
        if self.centralWidget().isHidden() is False:
            self.centralWidget().hide()

        dock = QtWidgets.QDockWidget("Image" + str(self.imageManager.rowCount()), self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(imageView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.show()
        dock.raise_()

        print("Added to Model:", self.imageManager.images)

    def saveFile(self):
        print("Save file functionality...")

    def exitApp(self):
        self.close()

    def aboutDialog(self):
        print("Show about dialog...")


def startGui():
    app = QtWidgets.QApplication(sys.argv)
    # Remove external stylesheet to revert to default Qt styling
    window = MainGUI()
    window.showMaximized()
    window.show()
    app.exec()


if __name__ == "__main__":
    startGui()
