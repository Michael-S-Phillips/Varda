"""

"""

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
from core.data import ProjectContext

# local imports


class BandViewModel(QObject):
    sigBandChanged = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = imageIndex
        self.bandIndex = 0
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self._handleDataChanged)

    def selectBand(self, bandIndex):
        self.bandIndex = bandIndex
        self.sigBandChanged.emit()

    def getSelectedBand(self):
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getBandRange(self):
        return self.proj.getImage(self.index).metadata.bandCount - 1

    def updateBand(self, r, g, b):
        # we cast the values to ints to floor them, since band values need to be ints
        self.proj.updateBand(self.index, self.bandIndex, r=int(r), g=int(g), b=int(b))

    def _handleDataChanged(self, index, changeType):
        if index != self.index:
            return
        if changeType != ProjectContext.ChangeType.BAND:
            return
        self.sigBandChanged.emit()
