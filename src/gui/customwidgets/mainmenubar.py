# standard library
import logging

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QWidget, QMenuBar, QMenu
from PyQt6.QtCore import QObject

# local imports

logger = logging.getLogger(__name__)


class MainMenuBar(QMenuBar):
    
    sigSaveProject = QtCore.pyqtSignal()
    sigOpenProject = QtCore.pyqtSignal()

    sigImportFile = QtCore.pyqtSignal()
    sigExitApp = QtCore.pyqtSignal()
    sigAboutDialog = QtCore.pyqtSignal()
    
    def __init__(self, imageManager=None, parent=None):
        super(MainMenuBar, self).__init__(parent)
        self.imageManager = imageManager
        self.initMenuBar()
        
    def initMenuBar(self):
        self.initFileMenu()
        self.initHelpmenu()
        
        
    def initFileMenu(self):
        fileMenu = self.addMenu('File')
        if fileMenu is None:
            logger.error("failed to create file menu")
            return
        
        fileMenu.addAction('Open Project', self.sigOpenProject)
        recentMenu = fileMenu.addMenu('Open Recent')

        fileMenu.addAction('Save', self.sigSaveProject)
        importMenu = fileMenu.addMenu('Import')
        
        if importMenu is None:
            logger.error("failed to create import menu")
            return
            
        importMenu.addAction('Import Image', self.sigImportFile)
        fileMenu.addAction('Exit', self.sigExitApp)
    
    def initRecentMenu(self):
        pass
        
    def initHelpmenu(self):
        helpMenu = self.addMenu('Help')
        if helpMenu is None:
            logger.error("failed to create help menu")
            return
        helpMenu.addAction('About', self.sigAboutDialog)
