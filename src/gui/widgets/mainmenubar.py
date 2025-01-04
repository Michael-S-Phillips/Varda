# standard library
import logging

# third party imports
from PyQt6 import QtCore
from PyQt6.QtWidgets import QMenuBar, QMenu

# local imports


logger = logging.getLogger(__name__)


class MainMenuBar(QMenuBar):
    """Menubar widget. This is mainly to move all the code constructing the menubar
    to its own class, to keep mainGUI clean.
    """

    sigSaveProject = QtCore.pyqtSignal()
    sigOpenProject = QtCore.pyqtSignal()
    sigImportFile = QtCore.pyqtSignal()
    sigExitApp = QtCore.pyqtSignal()
    sigAboutDialog = QtCore.pyqtSignal()

    def __init__(self, imageManager=None, parent=None):
        super().__init__(parent)
        self.imageManager = imageManager
        self.initUI()

    def initUI(self):
        self.addMenu(self.initFileMenu())
        self.addMenu(self.initHelpmenu())

    # Note: adding "self" as the parent of the QMenu is important, to keep it from
    # being garbage collected immediately
    def initFileMenu(self):
        fileMenu = QMenu("File", self)
        fileMenu.addMenu(self.initImportMenu())
        fileMenu.addAction("Open Project", self.sigOpenProject)
        fileMenu.addAction("Save", self.sigSaveProject)
        fileMenu.addAction("Exit", self.sigExitApp)
        return fileMenu

    def initImportMenu(self):
        importMenu = QMenu("Import", self)
        importMenu.addAction("Import Image", self.sigImportFile)
        return importMenu

    def initHelpmenu(self):
        helpMenu = QMenu("Help", self)
        helpMenu.addAction("About", self.sigAboutDialog)
        return helpMenu
