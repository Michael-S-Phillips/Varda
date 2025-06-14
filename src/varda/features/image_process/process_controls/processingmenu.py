# standard library
import logging

# third party imports
from PyQt6.QtWidgets import QMenu

# local imports
from varda.features.image_process.processes.imageprocess import ImageProcess

logger = logging.getLogger(__name__)


class ProcessingMenu(QMenu):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.refreshProcessingMenu()

    def refreshProcessingMenu(self):

        self.clear()
        for process in ImageProcess.subclasses:
            print("process being added to menu:", process)
            self.addAction(
                process.__name__, lambda p=process: self.openProcessControlMenu(p)
            )
