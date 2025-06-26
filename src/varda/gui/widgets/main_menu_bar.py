# standard library
import logging

# third party imports
from PyQt6 import QtCore
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import QMenuBar, QMenu

# local imports
import varda

logger = logging.getLogger(__name__)


class MainMenuBar(QMenuBar):
    """Menubar widget. This is mainly to move all the code constructing the menubar
    to its own class, to keep mainGUI clean.
    """

    sigSaveProject = QtCore.pyqtSignal()
    sigSaveProjectAs = QtCore.pyqtSignal()
    sigOpenProject = QtCore.pyqtSignal()
    sigOpenProcessingMenu = QtCore.pyqtSignal()
    sigImportFile = QtCore.pyqtSignal()
    sigExitApp = QtCore.pyqtSignal()
    sigAboutDialog = QtCore.pyqtSignal()
    sigLoadDebugProject = QtCore.pyqtSignal()
    sigDumpProjectData = QtCore.pyqtSignal()

    # NEW DUAL IMAGE SIGNALS
    sigOpenDualImageView = QtCore.pyqtSignal()
    sigLinkSelectedImages = QtCore.pyqtSignal()
    sigUnlinkSelectedImages = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()

    def _initUI(self):
        self._initFileMenu()
        self._initViewMenu()  # NEW: Add View menu
        self._initHelpmenu()
        self._initDebugMenu()
        self._initProcessMenu()

        self._initPluginMenu()


    # Note: adding "self" as the parent of the QMenu is important, to keep it from
    # being garbage collected immediately
    def _initFileMenu(self):
        fileMenu = QMenu("File", self)

        importMenu = QMenu("Import", self)
        importMenu.addAction("Import Image", QKeySequence("Ctrl+N"), self.sigImportFile)
        fileMenu.addMenu(importMenu)

        fileMenu.addAction("Open...", QKeySequence("Ctrl+O"), self.sigOpenProject)
        # fileMenu.addMenu(self._initOpenRecentMenu())
        fileMenu.addAction("Save", QKeySequence("Ctrl+S"), self.sigSaveProject)
        # fileMenu.addAction("Save As..", self.sigSaveProjectAs)
        fileMenu.addAction("Exit", self.sigExitApp)
        self.addMenu(fileMenu)
        return fileMenu

    # NEW VIEW MENU FOR DUAL IMAGE FUNCTIONALITY
    def _initViewMenu(self):
        viewMenu = QMenu("View", self)

        # Dual Image submenu
        dualImageMenu = QMenu("Dual Image", self)
        dualImageMenu.addAction(
            "Open Dual View...", QKeySequence("Ctrl+D"), self.sigOpenDualImageView
        )
        dualImageMenu.addSeparator()
        dualImageMenu.addAction(
            "Link Selected Images", QKeySequence("Ctrl+L"), self.sigLinkSelectedImages
        )
        dualImageMenu.addAction(
            "Unlink Selected Images",
            QKeySequence("Ctrl+U"),
            self.sigUnlinkSelectedImages,
        )

        viewMenu.addMenu(dualImageMenu)
        
        self.addMenu(viewMenu)

    def _initHelpmenu(self):
        helpMenu = QMenu("Help", self)
        helpMenu.addAction("About", self.sigAboutDialog)
        self.addMenu(helpMenu)

    def _initDebugMenu(self):
        debugMenu = QMenu("Debug", self)
        # debugMenu.addAction("Load Debug Project", QKeySequence("F10"), self.sigLoadDebugProject)
        debugMenu.addAction(
            "Project Data Dump", QKeySequence("F12"), self.sigDumpProjectData
        )
        self.addMenu(debugMenu)

    def _initProcessMenu(self):
        processMenu = QMenu("Process", self)
        processMenu.addAction("Image Processing...", self.sigOpenProcessingMenu)
        self.addMenu(processMenu)

    def _initPluginMenu(self):
        # Get all plugin menus from the registry
        pluginMenu = QMenu("Plugins", self)

        pluginWidgets = varda.app.registry.widgets
        for name, widgetClass in pluginWidgets:
            logger.debug(f"Adding widget {name}, class {widgetClass}")
            action = QAction(name, self)
            action.triggered.connect(lambda : self.openWidget(widgetClass))
            pluginMenu.addAction(action)
            logger.debug(f"Added plugin menu item: {name}")
        self.addMenu(pluginMenu)

    def openWidget(self, widgetClass):
        """Open a widget in the main window."""
        logger.debug(f"Opening widget {widgetClass}")
        widget = widgetClass(self.parent())
        widget.show()

