"""

"""

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
from core.data import ProjectContext

# local imports


class HistogramViewModel(QObject):
    """Simple ViewModel for the stretch view/editor. This handles all the business
    logic and interaction with the ProjectContext.
    """

    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = imageIndex
        self.stretchIndex = 0
        self.bandIndex = 0
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self._handleDataChanged)

    def selectBand(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self.sigBandChanged.emit()

    def selectStretch(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self.sigStretchChanged.emit()

    def getSelectedBand(self):
        """requests the stretch corresponding to stretchIndex, and returns it."""
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getSelectedStretch(self):
        """requests the stretch corresponding to stretchIndex, and returns it."""
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    def getRasterFromBand(self):
        """Using the currently selected band, creates and returns a subset of the
        raster data so that it can be used as a standard rgb image."""
        band = self.getSelectedBand()
        return self.proj.getImage(self.index).raster[:, :, [band.r, band.g, band.b]]

    def updateStretch(self, minR, maxR, minG, maxG, minB, maxB):
        """tells the project to update the stretch configuration with new values."""
        self.proj.updateStretch(
            self.index,
            self.stretchIndex,
            name=None,
            minR=minR,
            maxR=maxR,
            minG=minG,
            maxG=maxG,
            minB=minB,
            maxB=maxB,
        )

    def _handleDataChanged(self, index, changeType):
        if index != self.index:
            return
        if changeType is ProjectContext.ChangeType.BAND:
            self.sigBandChanged.emit()
        elif changeType is ProjectContext.ChangeType.STRETCH:
            self.sigStretchChanged.emit()
