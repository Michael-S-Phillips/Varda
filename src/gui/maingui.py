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

# to do:
# update control panel in main gui so multiple instances are not created
# make control panel accessible for one image

from core.data.project_context import ProjectContext
from core.ui import ControlPanel
# local imports
from gui.widgets import StatusBar, MainMenuBar
from features import (
    image_view_raster,
    image_view_stretch,
    image_view_band,
    image_view_roi,
    all_images_view_list,
    image_view_histogram,
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
        self.rasterViewObj = None
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

        # # Initialize Control Panel with ProjectContext
        # self.controlPanel = ControlPanel(self, self.proj)
        # self.addDockWidget(
        #     Qt.DockWidgetArea.RightDockWidgetArea, self.controlPanel.tabsDock
        # )

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
        self.menuBar().sigImportFile.connect(self.loadImage)
        self.menuBar().sigExitApp.connect(self.exitApp)
        self.menuBar().sigSaveProject.connect(self.saveProject)
        self.menuBar().sigOpenProject.connect(self.loadProject)

        self.imageList.currentItemChanged.connect(self.onSelectedImageChanged)

    def onSelectedImageChanged(self, item):
        """
        Handle the selection of a new image and update the control panel.
        """
        # now, only after an image is selected a control panel is created

        if item is None:
            self.selectedImage = None
            return

        # Retrieve the selected image's index
        index = self.imageList.row(item)
        self.selectedImage = self.proj.getImage(index)

        controlPanel = self.proj.getControlPanel(index, self)

        # remove other control panels if they are active for other images
        for dock in self.findChildren(QtWidgets.QDockWidget):
            if dock.widget() and isinstance(dock.widget(), ControlPanel):
                dock.close()

        # one image control panel should be open at a time
        # todo: add to list of control panels. Open an exisiting image's control
        # panel, remove / add control panels to the main window
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, controlPanel.tabsDock
        )

        controlPanel.updateActiveImage(index)
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
        roiView = openView.addAction("ROI Table View")
        stretchView = openView.addAction("Stretch View")
        histogramView = openView.addAction("Histogram View")
        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        logger.debug(type(image))
        imageIndex = image.index
        rasterView.triggered.connect(lambda: self.openRasterView(imageIndex))
        bandView.triggered.connect(lambda: self.openBandView(imageIndex))
        roiView.triggered.connect(lambda: self.openROIView(imageIndex))
        stretchView.triggered.connect(lambda: self.openStretchView(imageIndex))
        histogramView.triggered.connect(lambda: self.openHistogramView(imageIndex))
        return contextMenu

    def openHistogramView(self, index):
        view = image_view_histogram.getHistogramView(self.proj, index, self)
        dock = QtWidgets.QDockWidget("Histogram Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def openRasterView(self, index):
        view = image_view_raster.getRasterView(self.proj, index, self)
        self.rasterViewObj = view
        self.setCentralWidget(view)
        return
        dock = QtWidgets.QDockWidget("Raster Editor", parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        # dock.setFloating(True)

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

    def openROIView(self, index):
        view = image_view_roi.getROIView(self.proj, index, self)
        view.viewModel.setRasterView(self.rasterViewObj)
        dock = QtWidgets.QDockWidget(parent=self)
        dock.setAllowedAreas(QtCore.Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(view)
        self.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

    def loadImage(self, filePath=None):
        self.proj.loadNewImage(filePath)

    def saveProject(self):
        fileName = QtWidgets.QFileDialog.getSaveFileName(
            None, "Save File", "", "Varda project file (" "*.varda)"
        )
        if not fileName[0]:
            return
        self.proj.saveProject(fileName[0])

    def loadProject(self):
        fileName = QtWidgets.QFileDialog.getOpenFileName(
            None, "Open File", "", "Varda project file (" "*.varda)"
        )
        if not fileName[0]:
            return
        self.proj.loadProject(fileName[0])

    def exitApp(self):
        self.close()

    @override
    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))


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
