from pathlib import Path
import logging
import sys
import asyncio

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from qasync import QEventLoop, QApplication

from core.data import ProjectContext
from core.ui import ControlPanel
from gui.widgets import StatusBar, MainMenuBar
from features import (
    image_view_raster,
    image_view_stretch,
    image_view_band,
    image_view_roi,
    all_images_view_list,
    image_view_histogram,
)
import core.utilities.debug as debug

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self, proj: ProjectContext):
        super().__init__()

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("../img/logo.svg"))

        self.proj = proj
        self.selectedImage = None
        self.imageList = None
        self.currControlPanel = None
        self.controlPanels = {}  # image index -> ControlPanel
        self.rasterViews = {}  # image index -> RasterView
        self.roiViews = {}
        self.openROIViews = []  # Track all open ROI views - ADDED THIS LINE

        self.initUI()
        self.connectSignals()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setMenuBar(MainMenuBar())
        self.setStatusBar(StatusBar(self.proj))

        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = all_images_view_list.newList(self.proj, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        # Raster container
        self.rasterContainer = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.rasterContainer)

        # Starting screen label
        self.startingScreen = self.getStartingScreenWidget()
        self.rasterContainer.addWidget(self.startingScreen)

    def getStartingScreenWidget(self):
        label = QtWidgets.QLabel("Go to File->Import to open your first image!", parent=self)
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
        self.menuBar().sigImportFile.connect(self.proj.loadNewImage)
        self.menuBar().sigExitApp.connect(self.exitApp)
        self.menuBar().sigSaveProject.connect(self.proj.saveProject)
        self.menuBar().sigOpenProject.connect(self.proj.loadProject)
        self.menuBar().sigDumpProjectData.connect(lambda: debug.ProjectContextDataTable(self.proj, self))

        self.imageList.itemClicked.connect(self.onSelectedImageChanged)

    def onSelectedImageChanged(self, item):
        if item is None:
            self.selectedImage = None
            return

        index = self.imageList.row(item)
        self.selectedImage = self.proj.getImage(index)

        print(f"[DEBUG] Selected new image: {self.selectedImage.metadata.name} (index {self.selectedImage.index})")

        # Control Panel
        if self.currControlPanel:
            self.currControlPanel.tabsDock.hide()

        if index not in self.controlPanels:
            panel = ControlPanel(self)
            panel.updateActiveImage(self.selectedImage.index)
            self.controlPanels[index] = panel
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, panel.tabsDock)
        else:
            panel = self.controlPanels[index]

        self.currControlPanel = panel
        panel.tabsDock.show()

        # Raster View
        self.showRasterView(index)

        # Update any open ROI views
        self.updateAllROIViews(index)

    def showRasterView(self, index):
        print(f"[DEBUG] Showing RasterView for image {index}")
        for view in self.rasterViews.values():
            view.hide()

        if index not in self.rasterViews:
            view = image_view_raster.getRasterView(self.proj, index, self)
            self.rasterContainer.addWidget(view)
            self.rasterViews[index] = view
        else:
            view = self.rasterViews[index]

        self.rasterContainer.setCurrentWidget(view)
        view.show()

        # 🔗 Connect pixel click to control panel
        if self.currControlPanel:
            view.sigImageClicked.connect(self.currControlPanel.updatePixelPlotFromCrosshair)

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

        rasterView.triggered.connect(lambda: self.showRasterView(imageIndex))
        bandView.triggered.connect(lambda: self.openBandView(imageIndex))
        roiView.triggered.connect(lambda: self.openROIView(imageIndex))
        stretchView.triggered.connect(lambda: self.openStretchView(imageIndex))
        histogramView.triggered.connect(lambda: self.openHistogramView(imageIndex))
        return contextMenu

    def openROIView(self, image_index):
        print(f"[DEBUG] openROIView called with index: {image_index}")
        view = image_view_roi.getROIView(self.proj, image_index, self)

        # Set raster view reference if available
        if image_index in self.rasterViews:
            raster_view = self.rasterViews[image_index]
            view.viewModel.setRasterView(raster_view)

        dock = QtWidgets.QDockWidget("ROI Table", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

        # Store reference to the ROI view and its dock
        view_info = {"view": view, "dock": dock}
        self.openROIViews.append(view_info)

        # Connect close event to remove from tracking when dock is closed
        dock.destroyed.connect(lambda: self._removeROIView(view_info))

        return view

    def _removeROIView(self, view_info):
        """Helper method to remove a ROI view from tracking when closed."""
        if view_info in self.openROIViews:
            self.openROIViews.remove(view_info)
            print(f"[DEBUG] Removed ROI view from tracking. Remaining views: {len(self.openROIViews)}")

    def updateAllROIViews(self, current_image_index):
        """Update all open ROI views to show data for the current image."""
        if not hasattr(self, 'openROIViews') or not self.openROIViews:
            print("[DEBUG] No open ROI views to update")
            return

        print(f"[DEBUG] Updating {len(self.openROIViews)} open ROI views to show image {current_image_index}")

        # Update all open ROI views
        for view_info in self.openROIViews:
            roi_view = view_info["view"]

            # Update the image index in the view model
            roi_view.viewModel.updateImageIndex(current_image_index)

            # Update raster view reference if available
            if current_image_index in self.rasterViews:
                raster_view = self.rasterViews[current_image_index]
                roi_view.viewModel.setRasterView(raster_view)

    def openBandView(self, image_index):
        from features.image_view_band import BandManager
        view = BandManager(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Band View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

    def openStretchView(self, image_index):
        from features.image_view_stretch import getStretchView
        view = getStretchView(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Stretch View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

    def openHistogramView(self, image_index):
        from features.image_view_histogram import getHistogramView
        view = getHistogramView(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Histogram View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

    def exitApp(self):
        print("[DEBUG] Exit App triggered")
        self.close()

    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.proj.loadNewImage(str(Path(event.mimeData().urls()[0].toLocalFile())))


def startGui(proj: ProjectContext):
    app = QApplication(sys.argv)

    eventLoop = QEventLoop(app)
    asyncio.set_event_loop(eventLoop)

    window = MainGUI(proj)
    window.showMaximized()
    window.show()

    with eventLoop:
        eventLoop.run_forever()