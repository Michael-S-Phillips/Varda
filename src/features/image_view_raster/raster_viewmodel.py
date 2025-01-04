# third party imports
from PyQt6.QtCore import QObject, pyqtSignal

# local imports
from core.data import ProjectContext


class RasterViewModel(QObject):
    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = imageIndex
        self.bandIndex = 0
        self.stretchIndex = 0
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self._handleDataChanged)

    def selectBand(self, bandIndex):
        self.bandIndex = bandIndex
        self.sigBandChanged.emit()

    def getSelectedBand(self):
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getRasterFromBand(self):
        band = self.getSelectedBand()
        return self.proj.getImage(self.index).raster[:, :, [band.r, band.g, band.b]]

    def selectStretch(self, stretchIndex):
        self.stretchIndex = stretchIndex
        self.sigStretchChanged.emit()

    def getSelectedStretch(self):
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    def _handleDataChanged(self, index, changeType):
        if index != self.index:
            return
        if changeType is ProjectContext.ChangeType.BAND:
            self.sigBandChanged.emit()
        elif changeType is ProjectContext.ChangeType.STRETCH:
            self.sigStretchChanged.emit()
