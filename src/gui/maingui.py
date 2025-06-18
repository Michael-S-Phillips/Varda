from pathlib import Path
import logging
import sys
import asyncio
from typing import Dict

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, QObject
from qasync import QEventLoop, QApplication

from core.data import ProjectContext
from core.ui import ControlPanel
from features.image_view_raster.raster_view import RasterView
from features.image_process.process_controls.processingmenu import ProcessingMenu
from features.image_process.process_controls.processdialog import ProcessDialog
from features.image_process.processes.imageprocess import ImageProcess
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
        self.setWindowIcon(QIcon("img/logo.svg"))

        self.proj = proj
        self.selectedImage = None
        self.imageList = None
        self.currControlPanel = None
        self.controlPanels: Dict[int, ControlPanel] = {}  # image index -> ControlPanel
        self.rasterViews: Dict[int, RasterView] = {}  # image index -> RasterView
        self.roiViews = {}

        # Track all open windows
        self.childWindows = []  # List of all child windows/widgets we need to track
        self.pixelPlotWindows = []  # Track all pixel plot windows specifically

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
        label = QtWidgets.QLabel(
            "Go to File->Import to open your first image!", parent=self
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
        self.menuBar().sigImportFile.connect(self.proj.loadNewImage)
        self.menuBar().sigExitApp.connect(self.exitApp)
        self.menuBar().sigSaveProject.connect(self.proj.saveProject)
        self.menuBar().sigOpenProject.connect(self.proj.loadProject)
        self.menuBar().sigDumpProjectData.connect(
            lambda: debug.ProjectContextDataTable(self.proj, self)
        )

        self.menuBar().sigOpenProcessingMenu.connect(self.openProcessingMenu)

        self.imageList.itemClicked.connect(self.onSelectedImageChanged)

        self.proj.sigDataChanged.connect(self.onProjectDataChanged)

    def onSelectedImageChanged(self, item):
        if item is None:
            self.selectedImage = None
            return

        index = self.imageList.row(item)
        self.selectedImage = self.proj.getImage(index)

        print(
            f"[DEBUG] Selected new image: {self.selectedImage.metadata.name} (index {self.selectedImage.index})"
        )

        # Raster View
        rasterView = self.showRasterView(index)

        # Control Panel
        if self.currControlPanel:
            self.currControlPanel.tabsDock.hide()

        if index not in self.controlPanels:
            panel = ControlPanel(self.proj, index, rasterView)
            # panel.updateActiveImage(self.selectedImage.index)
            self.controlPanels[index] = panel
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, panel.tabsDock)
        else:
            panel = self.controlPanels[index]

        self.currControlPanel = panel
        panel.tabsDock.show()

        # Update any open ROI views
        self.updateAllROIViews(index)

    def showRasterView(self, index):
        print(f"[DEBUG] Showing RasterView for image {index}")
        for view in self.rasterViews.values():
            view.hide()

        if index not in self.rasterViews:
            view = image_view_raster.getRasterView(self.proj, index, self)
            logger.debug("New RasterView created!")
            self.rasterContainer.addWidget(view)
            self.rasterViews[index] = view
        else:
            view = self.rasterViews[index]

        self.rasterContainer.setCurrentWidget(view)
        view.show()

        return view

    # TODO: I think we can delete the context menu stuff since we have the control panel. Relevant methods tagged below

    # TODO: Delete?
    def contextMenuEvent(self, event):
        localPos = self.imageList.mapFromGlobal(event.globalPos())
        item = self.imageList.itemAt(localPos)
        index = self.imageList.indexFromItem(item)
        if index.isValid():
            contextMenu = self.createContextMenu(index)
            contextMenu.exec(event.globalPos())
        else:
            print("No item selected")

    # TODO: Delete?
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

    # TODO: Delete?
    def openROIView(self, image_index):
        """Open ROI view and properly connect it to RasterView"""
        print(f"[DEBUG] openROIView called with index: {image_index}")
        view = image_view_roi.getROIView(self.proj, image_index, self)

        # Set raster view reference if available
        if image_index in self.rasterViews:
            raster_view = self.rasterViews[image_index]
            view.viewModel.setRasterView(raster_view)

            # Connect signals/slots for updates in both directions
            if hasattr(view, "roiSelectionChanged"):
                view.roiSelectionChanged.connect(
                    lambda roi_index: (
                        raster_view.highlightROI(roi_index)
                        if hasattr(raster_view, "highlightROI")
                        else None
                    )
                )

        dock = QtWidgets.QDockWidget("ROI Table", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        dock.setFloating(True)

        # Store the view and track the dock widget
        self.childWindows.append(dock)
        if not hasattr(self, "roiViews"):
            self.roiViews = {}
        self.roiViews[image_index] = view

        # Connect close event to remove from tracking when dock is closed
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

        return view

    def removeChildWindow(self, window):
        """Remove a window from tracking when it's closed."""
        if window in self.childWindows:
            self.childWindows.remove(window)
            logger.debug(
                f"Removed window from tracking. Remaining windows: {len(self.childWindows)}"
            )

    def updateAllROIViews(self, current_image_index):
        """Update all open ROI views to show data for the current image."""
        for window in self.childWindows:
            if hasattr(window, "widget") and window.widget():
                widget = window.widget()
                if hasattr(widget, "viewModel") and hasattr(
                    widget.viewModel, "updateImageIndex"
                ):
                    widget.viewModel.updateImageIndex(current_image_index)

                    # Update raster view reference if available
                    if (
                        hasattr(widget.viewModel, "setRasterView")
                        and current_image_index in self.rasterViews
                    ):
                        widget.viewModel.setRasterView(
                            self.rasterViews[current_image_index]
                        )

    # TODO: Delete?
    def openBandView(self, image_index):
        from features.image_view_band import BandManager

        view = BandManager(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Band View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # Track the dock widget
        self.childWindows.append(dock)
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

    # TODO: Delete?
    def openStretchView(self, image_index):
        from features.image_view_stretch import getStretchView

        view = getStretchView(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Stretch View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # Track the dock widget
        self.childWindows.append(dock)
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

    # TODO: Delete?
    def openHistogramView(self, image_index):
        from features.image_view_histogram import getHistogramView

        view = getHistogramView(self.proj, image_index, self)
        dock = QtWidgets.QDockWidget("Histogram View", self)
        dock.setWidget(view)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        dock.setFloating(True)

        # Track the dock widget
        self.childWindows.append(dock)
        dock.destroyed.connect(lambda: self.removeChildWindow(dock))

    def openProcessingMenu(self):
        """Open the image processing menu for the currently selected image."""
        if self.selectedImage is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Image Selected",
                "Please select an image before opening the processing menu.",
            )
            return

        # Create processing menu
        processingMenu = ProcessingMenu(self)

        # Connect menu actions to process execution
        def handle_process_action(action):
            # Find process class by action text
            action_text = action.text()
            for process_class in ImageProcess.subclasses:
                if process_class.__name__ == action_text:
                    # Create process dialog with proper parent and project context
                    processDialog = ProcessDialog(self.selectedImage)
                    processDialog.setParent(self)  # Ensure proper parent chain
                    processDialog.project_context = self.proj  # Direct assignment
                    processDialog.sigProcessFinished.connect(self.onProcessFinished)
                    processDialog.openProcessControlMenu(process_class)
                    break

        processingMenu.triggered.connect(handle_process_action)

        # Show menu at cursor position
        cursor_pos = QCursor.pos()
        processingMenu.exec(cursor_pos)

    def onProcessFinished(self):
        """Handle when an image process finishes - refresh the image list."""
        print("Image processing completed!")

    def onProjectDataChanged(self, index, changeType, changeModifier=None):
        """Handle when project data changes (like new images being added)."""
        if changeType == self.proj.ChangeType.IMAGE and changeModifier == self.proj.ChangeModifier.ADD:
            print(f"New image added at index {index}")

    # TODO: Delete?
    def trackPixelPlotWindow(self, window):
        """Track a pixel plot window."""
        if window not in self.pixelPlotWindows:
            self.pixelPlotWindows.append(window)
            # Connect close event to remove from tracking
            window.destroyed.connect(lambda: self.removePixelPlotWindow(window))

    # TODO: Delete?
    def removePixelPlotWindow(self, window):
        """Remove a pixel plot window from tracking."""
        if window in self.pixelPlotWindows:
            self.pixelPlotWindows.remove(window)

    def closeAllChildWindows(self):
        """Close all child windows before shutting down."""
        # Close all tracked child windows
        for window in self.childWindows[
            :
        ]:  # Use a copy of the list since it will be modified during iteration
            if window and window.isVisible():
                window.close()

        # Close all pixel plot windows
        for window in self.pixelPlotWindows[:]:
            if window and window.isVisible():
                window.close()

        # Close any control panels
        for panel in self.controlPanels.values():
            if hasattr(panel, "pixelPlotPopup") and panel.pixelPlotPopup:
                panel.pixelPlotPopup.close()

        # Clear tracking lists
        self.childWindows.clear()
        self.pixelPlotWindows.clear()

        logger.info("All child windows closed")

    def exitApp(self):
        """Properly shut down the application by closing all windows."""
        logger.info("Exiting application...")

        # Close all child windows first
        self.closeAllChildWindows()

        # Then close the main window
        self.close()

        # Force application to quit after a short delay if it hasn't already
        QtCore.QTimer.singleShot(500, lambda: QtWidgets.QApplication.quit())

    def closeEvent(self, event):
        """Handle the window close event to ensure proper cleanup."""
        logger.info("Main window close event triggered")

        # Close all child windows first
        self.closeAllChildWindows()

        # Accept the close event to allow the window to close
        event.accept()

    def dragEnterEvent(self, event, **kwargs):
        event.acceptProposedAction()

    def dropEvent(self, event, **kwargs):
        self.statusBar().showLoadingMessage()
        self.proj.loadNewImage(str(Path(event.mimeData().urls()[0].toLocalFile())))


def startGui(proj: ProjectContext):
    app = QApplication(sys.argv)

    # Set the application name and organization
    app.setApplicationName("Varda")
    app.setOrganizationName("Varda")

    # Set up a signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}. Shutting down...")
        app.quit()

    # Set up the event loop
    eventLoop = QEventLoop(app)
    asyncio.set_event_loop(eventLoop)

    # Create and show the main window
    window = MainGUI(proj)
    window.showMaximized()
    window.show()

    # Register the cleanup handler for when the application is about to quit
    app.aboutToQuit.connect(lambda: logger.info("Application is about to quit"))

    # Run the event loop until it's stopped
    with eventLoop:
        eventLoop.run_forever()
