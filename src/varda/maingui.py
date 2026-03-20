from pathlib import Path
import logging
from typing import Optional

from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon, QCursor
from PyQt6.QtCore import Qt, pyqtSlot

from varda.common.ui import DetachableTabWidget
# from varda.project import ProjectContext

from varda.workspaces import GeneralImageAnalysisWorkflow
from varda.image_processing.process_controls.processingmenu import ProcessingMenu
from varda.image_processing.process_controls.processdialog import ProcessDialog
from varda.workspaces.dual_image_view.dual_image_types import DualImageMode
from varda.workspaces.dual_image_view.dual_image_selection_dialog import (
    DualImageSelectionDialog,
)
from varda.all_images_view_list import all_images_view_list

logger = logging.getLogger(__name__)


class MainGUI(QtWidgets.QMainWindow):
    def __init__(self, app, menubar, statusbar):
        super().__init__()

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("resources/logo.svg"))
        self.setMenuBar(menubar)
        self.setStatusBar(statusbar)
        self.app = app
        # self.proj = app.proj
        self.selectedImage = None
        self.imageList = None
        self.rasterViews = {}  # image index -> RasterView

        # Track all open windows
        self.childWindows = []  # List of all child windows/widgets we need to track

        self.initUI()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = all_images_view_list.newList(self.app.images, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        self.centralTabs = DetachableTabWidget(self)
        self.setCentralWidget(self.centralTabs)
        # # Starting screen label
        # startingScreen = QtWidgets.QLabel(
        #     "Go to File->Import to open your first image!", parent=self
        # )
        # startingScreen.setStyleSheet("font-size: 20px;")
        # startingScreen.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.setCentralWidget(startingScreen)

    def newDock(self, title, widget, dockArea):
        dock = QtWidgets.QDockWidget(title, self)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        dock.setWidget(widget)
        self.addDockWidget(dockArea, dock)
        return dock

    def addTab(self, widget, title=None):
        """Add a new tab to the central tab widget."""
        self.childWindows.append(widget)
        self.centralTabs.addTab(widget, title)

    def closeAllChildWindows(self):
        """Close all child windows before shutting down."""
        # Close all tracked child windows
        for window in self.childWindows[
            :
        ]:  # Use a copy of the list since it will be modified during iteration
            if window and window.isVisible():
                window.close()

        # Clear tracking lists
        self.childWindows.clear()

        logger.info("All child windows closed")

    def closeEvent(self, event):
        """Handle the window close event to ensure proper cleanup."""
        logger.info("Main window close event triggered")

        # Close all child windows first
        self.closeAllChildWindows()

        # Accept the close event to allow the window to close
        event.accept()
