# third party imports
from PyQt6.QtCore import QObject, pyqtSignal

# local imports
from core.data import ProjectContext


class RasterViewModel(QObject):
    """Simple viewmodel for the RasterView. Can manage band and stretch selections,
    and generate an rgb image based on the raster data and currently selected band."""

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
        """selects a new band from the image."""
        self.bandIndex = bandIndex
        self.sigBandChanged.emit()

    def getSelectedBand(self):
        """returns the currently selected band from the image"""
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getRasterFromBand(self):
        """Using the currently selected band, creates and returns a subset of the
        raster data so that it can be used as a standard rgb image."""
        band = self.getSelectedBand()
        return self.proj.getImage(self.index).raster[:, :, [band.r, band.g, band.b]]

    def selectStretch(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self.sigStretchChanged.emit()

    def getSelectedStretch(self):
        """returns the currently selected stretch from the image"""
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    def _handleDataChanged(self, index, changeType):
        if index != self.index:
            return
        if changeType is ProjectContext.ChangeType.BAND:
            self.sigBandChanged.emit()
        elif changeType is ProjectContext.ChangeType.STRETCH:
            self.sigStretchChanged.emit()

    def getFullDataCube(self):
        """Returns the full hyperspectral data cube from the image."""
        return self.proj.getImage(self.index).raster
