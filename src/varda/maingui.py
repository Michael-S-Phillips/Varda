from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from app_model.backends.qt import QModelMainWindow
from varda.common.ui import DetachableTabWidget
from varda.all_images_view_list.imageview_list import ImageListWidget

if TYPE_CHECKING:
    from varda.app import VardaApplication

logger = logging.getLogger(__name__)


class MainGUI(QModelMainWindow):
    def __init__(self, app: VardaApplication):
        super().__init__(app)

        self.setWindowTitle("Varda")
        self.setWindowIcon(QIcon("resources/logo.svg"))
        self.app = app
        self.selectedImage = None
        self.imageList = None
        self.rasterViews = {}  # image index -> RasterView

        # Track all open windows
        self.childWindows = []

        self.initUI()

        logger.info("MainGUI Initialized")

    def initUI(self):
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas,
            QtWidgets.QTabWidget.TabPosition.North,
        )

        self.imageList = ImageListWidget(self.app.images, self)
        self.newDock("Image List", self.imageList, Qt.DockWidgetArea.LeftDockWidgetArea)

        self.centralTabs = DetachableTabWidget(self)
        self.setCentralWidget(self.centralTabs)

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
        for window in self.childWindows[:]:
            if window and window.isVisible():
                window.close()

        self.childWindows.clear()

        logger.info("All child windows closed")

    def closeEvent(self, event):
        """Handle the window close event to ensure proper cleanup."""
        logger.info("Main window close event triggered")
        self.closeAllChildWindows()
        event.accept()
