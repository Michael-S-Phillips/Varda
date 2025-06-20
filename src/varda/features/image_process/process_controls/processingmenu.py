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
        self.setTitle("Image Processing")
        self.refreshProcessingMenu()

    def refreshProcessingMenu(self):
        self.clear()
        for process in ImageProcess.subclasses:
            print("process being added to menu:", process)
            # Create action with the class name as text
            action = self.addAction(process.__name__)
            # Store the process class in the action data
            action.setData(process)
