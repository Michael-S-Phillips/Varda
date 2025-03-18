# standard library
import logging

# third party imports
from PyQt6 import QtCore
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenuBar, QMenu

# local imports

logger = logging.getLogger(__name__)


class MainMenuBar(QMenuBar):
    """Menubar widget. This is mainly to move all the code constructing the menubar
    to its own class, to keep mainGUI clean.
    """

    sigSaveProject = QtCore.pyqtSignal()
    sigSaveProjectAs = QtCore.pyqtSignal()
    sigOpenProject = QtCore.pyqtSignal()
    sigImportFile = QtCore.pyqtSignal()
    sigExitApp = QtCore.pyqtSignal()
    sigAboutDialog = QtCore.pyqtSignal()
    sigLoadDebugProject = QtCore.pyqtSignal()
    sigDumpProjectData = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()

    def _initUI(self):
        self.addMenu(self._initFileMenu())
        self.addMenu(self._initHelpmenu())
        self.addMenu(self._initDebugMenu())

    # Note: adding "self" as the parent of the QMenu is important, to keep it from
    # being garbage collected immediately
    def _initFileMenu(self):
        fileMenu = QMenu("File", self)
        fileMenu.addMenu(self._initImportMenu())
        fileMenu.addAction("Open...", QKeySequence("Ctrl+O"), self.sigOpenProject)
        # fileMenu.addMenu(self._initOpenRecentMenu())
        fileMenu.addAction("Save", QKeySequence("Ctrl+S"), self.sigSaveProject)
        # fileMenu.addAction("Save As..", self.sigSaveProjectAs)
        fileMenu.addAction("Exit", self.sigExitApp)
        return fileMenu

    def _initImportMenu(self):
        importMenu = QMenu("Import", self)
        importMenu.addAction("Import Image", QKeySequence("Ctrl+N"), self.sigImportFile)
        return importMenu

    def _initOpenRecentMenu(self):
        openRecentMenu = QMenu("Open Recent", self)
        openRecentMenu.addAction("Open", self.sigOpenProject)
        return openRecentMenu

    def _initHelpmenu(self):
        helpMenu = QMenu("Help", self)
        helpMenu.addAction("About", self.sigAboutDialog)
        return helpMenu

    def _initDebugMenu(self):
        debugMenu = QMenu("Debug", self)
        debugMenu.addAction("Load Debug Project", self.sigLoadDebugProject)
        debugMenu.addAction("Project Data Dump", self.sigDumpProjectData)
        return debugMenu