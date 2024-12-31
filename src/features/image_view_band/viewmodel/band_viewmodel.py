"""

"""
# third party imports
from PyQt6.QtCore import QObject, pyqtSignal

# local imports
from core.entities import Image, Band


class BandViewModel(QObject):
    sigBandChanged = pyqtSignal(Band)

    def __init__(self, image: Image, parent=None):
        super().__init__(parent)
        self.selectedBand = 0
