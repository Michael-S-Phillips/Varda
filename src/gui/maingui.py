# standard library
import datetime
from pathlib import Path
import logging
import sys
import os
from typing import override

# third party imports
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QIcon
import pyqtgraph as pg


# local imports
from gui.imageloadingmanager import ImageLoadingManager
from .customwidgets.imagebasicstretcheditor import ImageBasicStretchEditor
from .customwidgets.imagebasicbandeditor import ImageBasicBandEditor
from .customwidgets.imagelistview import ImageListView
from .customwidgets.imagerasterdataviewer import ImageRasterDataViewer
from .customwidgets.controlpanel import ControlPanel
from .customwidgets.vstatusbar import VStatusBar
from .customwidgets.mainmenubar import MainMenuBar
from models.parametermodel import ParameterModel
from gui.imageloadingmanager import ImageLoadingManager
from models import ImageManager
import vardathreading

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
        pg.setConfigOptions(imageAxisOrder='row-major')
        logger.info("Started")
        

        self.imageManager = ImageManager()
        self.imageLoadingManager = ImageLoadingManager(self.imageManager)
        self.imageLoadingManager.sigImageLoaded.connect(self.onImageLoaded)
        
        self.initUI()
        
        logger.info("UI Initialized")
    def initUI(self):
        self.setupMenuBar()
        self.setStatusBar(VStatusBar())
        # make dock tabs appear on top
        self.setTabPosition(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
                            QtWidgets.QTabWidget.TabPosition.North)

        self.imageListViewDock = QtWidgets.QDockWidget("Image List", self)
        self.imageListViewDock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)


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


        # Create a central workspaceTabs
        self.setWindowIcon(QIcon("./img/logo.svg"))
        
    def setupMenuBar(self):
        menubar = MainMenuBar()
        self.setMenuBar(menubar)
        menubar.sigImportFile.connect(self.imageLoadingManager.openFileDialog)
        menubar.sigExitApp.connect(self.exitApp)

    @override
    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.imageLoadingManager.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def onImageLoaded(self, image):
        self.statusBar().loadingFinished()
        if image is None:
            return

        imageView = ImageRasterDataViewer(image)
        
        self.basicStretchEditor = ImageBasicStretchEditor(image)
        self.basicBandEditor = ImageBasicBandEditor(image)
        
        # remove initial prompt
        if self.centralWidget().isHidden() is False:
            self.centralWidget().hide()

        dock = QtWidgets.QDockWidget("Image" + str(self.imageManager.rowCount()), self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(imageView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.show()
        dock.raise_()

        print("Added to Model:", image)

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
