# standard library
from pathlib import Path
import logging
import sys
from typing import override

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon
import pyqtgraph as pg

# local imports
from gui.views import (ImageViewStretchEditor, ImageViewBandEditor,
                       ImageViewList, ImageViewRasterData)
from gui.widgets import ControlPanel, StatusBar, MainMenuBar

from models.imagemanager import ImageManager
from utilities import vardathreading, savesystem

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

        self.initUI()

        self.connectSignals()

        self.viewWindows = []
        logger.info("UI Initialized")

    def initUI(self):
        self.setupMenuBar()
        self.setStatusBar(StatusBar())
        # make dock tabs appear on top
        self.setTabPosition(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas,
                            QtWidgets.QTabWidget.TabPosition.North)

        self.imageListViewDock = QtWidgets.QDockWidget("Image List", self)
        self.imageListViewDock.setAllowedAreas(
            QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)

        self.imageListView = ImageViewList(self, self.imageManager)
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
        menubar.sigImportFile.connect(self.openFileDialog)
        menubar.sigExitApp.connect(self.exitApp)
        menubar.sigSaveProject.connect(self.saveProject)
        menubar.sigOpenProject.connect(self.loadProject)

    def connectSignals(self):
        self.imageListView.sigOpenRasterView.connect(self.openRasterView)
        self.imageListView.sigOpenStretchView.connect(self.openStretchView)
        self.imageListView.sigOpenBandView.connect(self.openBandView)

    def openRasterView(self, imageModel):
        view = ImageViewRasterData(imageModel)
        dock = QtWidgets.QDockWidget("Raster Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openStretchView(self, imageModel):
        view = ImageViewStretchEditor(imageModel)
        dock = QtWidgets.QDockWidget("Stretch Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openBandView(self, imageModel):
        view = ImageViewBandEditor(imageModel)
        dock = QtWidgets.QDockWidget(parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openFileDialog(self):
        # TODO: automatically determine all file types that are supported
        fileName = QtWidgets.QFileDialog.getOpenFileName(None,
                                                         "Open File", "",
                                                         "image file (*.hdr *.img "
                                                         "*.h5)")
        if fileName[0] is False:
            return

        self.loadImage(fileName[0])

    def loadImage(self, fileName):
        logger.info("Loading image: " + fileName)
        vardathreading.dispatchThreadProcess(self.onImageLoaded,
                                             self.imageManager.newImage, fileName)

    def onImageLoaded(self, image):
        self.statusBar().loadingFinished()
        if image is None:
            return

        imageView = ImageViewRasterData(image)

        # remove initial prompt
        if self.centralWidget().isHidden() is False:
            self.centralWidget().hide()

        dock = QtWidgets.QDockWidget("Image" + str(self.imageManager.rowCount()), self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(imageView)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.show()
        dock.raise_()

    def saveProject(self):
        fileName = QtWidgets.QFileDialog.getSaveFileName(None,
                                                         "Save File", "",
                                                         "Varda project file ("
                                                         "*.varda)")
        if not fileName[0]:
            return
        savesystem.saveProject(self.imageManager, fileName[0])

    def loadProject(self):
        fileName = QtWidgets.QFileDialog.getOpenFileName(None,
                                                         "Open File", "",
                                                         "Varda project file ("
                                                         "*.varda)")
        if not fileName[0]:
            return
        savesystem.loadProject(self.imageManager, fileName[0])

    def exitApp(self):
        self.close()

    @override
    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))


def startGui():
    app = QtWidgets.QApplication(sys.argv)
    # Remove external stylesheet to revert to default Qt styling
    window = MainGUI()
    window.showMaximized()
    window.show()
    app.exec()


if __name__ == "__main__":
    startGui()
