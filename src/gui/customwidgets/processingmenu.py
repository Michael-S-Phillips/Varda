# standard library
import logging

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QWidget, QMenuBar, QMenu
from PyQt6.QtCore import QObject

# local imports
from src.imageprocessing.imageprocess import ImageProcess
from src.gui.customwidgets.processdialog import ProcessDialog

logger = logging.getLogger(__name__)


class ProcessingMenu(QMenu):
    
    def __init__(self, parent=None):
        super(ProcessingMenu, self).__init__(parent)
        
        self.refreshProcessingMenu()
        
    def refreshProcessingMenu(self):

        self.clear()
        for process in ImageProcess.subclasses:
            print("process being added to menu:", process)
            self.addAction(process.__name__,
                                          lambda p=process: self.openProcessControlMenu(
                                              p))
            
    