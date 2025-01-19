# standard library
from pathlib import Path
import logging
import sys
from typing import override

# third party imports
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from qasync import QEventLoop, QApplication
import asyncio
import pyqtgraph as pg

from core.data.project_context import ProjectContext

# local imports
from gui.widgets import ControlPanel, StatusBar, MainMenuBar
from features import (
    image_view_raster,
    image_view_stretch,
    image_view_band,
    all_images_view_list,
    image_load,
)
import core.utilities as utils

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    """
    Creates the main window and layout for the GUI. Each GUI
    component is initialized (we will probably need to turn each
    component into a class attribute that is publicly accessible)
    """

    def __init__(self, proj: ProjectContext):
        super().__init__()
        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("../img/logo.svg"))

        self.proj = proj
        self.imageList = None
        self.selectedImage = None
        self.initUI()
        self.connectSignals()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setMenuBar(MainMenuBar())
        self.setStatusBar(StatusBar())

        # make dock tabs appear on top
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = all_images_view_list.newList(self.proj, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        # Initialize Control Panel with ProjectContext
        self.controlPanel = ControlPanel(self.proj)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.controlPanel.tabsDock
        )

        # set default central widget
        self.setCentralWidget(self.getStartingScreenWidget())

    def getStartingScreenWidget(self):
        label = QtWidgets.QLabel(
            "Go to File->import to open your first image!", parent=self
        )
        label.setStyleSheet("font-size: 20px;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def newDock(self, title, widget, dockArea):
        dock = QtWidgets.QDockWidget(title, self)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)
        self.addDockWidget(dockArea, dock)
        return dock

    def connectSignals(self):
        self.menuBar().sigImportFile.connect(
            lambda: asyncio.create_task(self.loadImage())
        )
        self.menuBar().sigExitApp.connect(self.exitApp)
        # menubar.sigSaveProject.connect(self.saveProject)
        # menubar.sigOpenProject.connect(self.loadProject)

        self.imageList.currentItemChanged.connect(self.onSelectedImageChanged)

    def onSelectedImageChanged(self, item):
        """
        Handle the selection of a new image and update the control panel.
        """
        if item is None:
            self.selectedImage = None
            self.controlPanel.updateActiveImage(None)
            return

        # Retrieve the selected image's index
        index = self.imageList.row(item)
        self.selectedImage = self.proj.getImage(index)
        self.controlPanel.updateActiveImage(index)
        print(f"Selected image updated: {self.selectedImage.metadata.name}")

    def contextMenuEvent(self, event):
        localPos = self.imageList.mapFromGlobal(event.globalPos())
        item = self.imageList.itemAt(localPos)
        index = self.imageList.indexFromItem(item)
        if index.isValid():
            contextMenu = self.createContextMenu(index)
            contextMenu.exec(event.globalPos())
        else:
            print("No item selected")

    def createContextMenu(self, index):
        contextMenu = QtWidgets.QMenu(self)
        openView = contextMenu.addMenu("Open View")
        rasterView = openView.addAction("RasterData View")
        bandView = openView.addAction("Band View")
        stretchView = openView.addAction("Stretch View")
        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        logger.debug(type(image))
        imageIndex = image.index
        rasterView.triggered.connect(lambda: self.openRasterView(imageIndex))
        bandView.triggered.connect(lambda: self.openBandView(imageIndex))
        stretchView.triggered.connect(lambda: self.openStretchView(imageIndex))
        return contextMenu

    def openRasterView(self, index):
        view = image_view_raster.getRasterView(self.proj, index, self)
        dock = QtWidgets.QDockWidget("Raster Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openStretchView(self, index):
        view = image_view_stretch.getStretchView(self.proj, index, self)
        dock = QtWidgets.QDockWidget("Stretch Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openBandView(self, index):
        view = image_view_band.getBandView(self.proj, index, self)
        dock = QtWidgets.QDockWidget(parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    async def loadImage(self):
        await image_load.loadNewImage(self.proj)

    # def onImageLoaded(self, image):
    #     self.statusBar().loadingFinished()
    #     if image is None:
    #         return
    #
    #     imageView = ImageViewRaster(image)
    #
    #     # remove initial prompt
    #     if self.centralWidget().isHidden() is False:
    #         self.centralWidget().hide()
    #
    #     dock = QtWidgets.QDockWidget("Image" + str(self.imageManager.rowCount()), self)
    #     dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
    #     dock.setWidget(imageView)
    #     self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    #     dock.show()
    #     dock.raise_()
    #
    def saveProject(self):
        fileName = QtWidgets.QFileDialog.getSaveFileName(
            None, "Save File", "", "Varda project file (" "*.varda)"
        )
        if not fileName[0]:
            return
        # TODO

    def loadProject(self):
        fileName = QtWidgets.QFileDialog.getOpenFileName(
            None, "Open File", "", "Varda project file (" "*.varda)"
        )
        if not fileName[0]:
            return

        # TODO

    def exitApp(self):
        self.close()

    # @override
    # def dragEnterEvent(self, event, **kwargs):
    #     event.acceptProposedAction()
    #
    # @override
    # def dropEvent(self, event, **kwargs):
    #     self.statusBar().showLoadingMessage()
    #     self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))


def startGui(proj: ProjectContext):
    """Main entrypoint for the GUI."""
    app = QApplication(sys.argv)

    eventLoop = QEventLoop(app)
    asyncio.set_event_loop(eventLoop)

    # Remove external stylesheet to revert to default Qt styling
    window = MainGUI(proj)
    window.showMaximized()
    window.show()
    with eventLoop:  # Ensures the loop runs and stops properly
        eventLoop.run_forever()
    # app.exec()
