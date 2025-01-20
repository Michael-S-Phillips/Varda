# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

# local imports
from core.data import ProjectContext


class ROIViewModel(QObject):
    """Simple ViewModel for ROI table.

    Handles all the logic/interaction with the ProjectContext.
    """

    #sigBandChanged = pyqtSignal(int, int, int)

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        
        self._connectSignals()


    def _connectSignals(self):
        pass

    # selectROI

    # getSelectedROI

    # loadROI data

    # handle ROI change (from project context)

    # def selectBand(self, bandIndex):
    #     """selects a new band from the image."""
    #     self.bandIndex = bandIndex
    #     self.sigBandChanged.emit()

    # def getSelectedBand(self):
    #     """requests the band corresponding to bandIndex, and returns it."""
    #     return self.proj.getImage(self.imageIndex).band[self.bandIndex]

    # def getBandCount(self):
    #     """gets the number of band values in the image."""
    #     return self.proj.getImage(self.imageIndex).metadata.bandCount - 1

    # def updateBand(self, r=None, g=None, b=None):
    #     """Begins a debounced band update. Since the slider value is constantly
    #     changing when being moved, this waits until the change is complete"""
    #     self._pendingBandValues = (
    #         int(r) if r else None,
    #         int(g) if g else None,
    #         int(b) if b else None,
    #     )
    #     if not self.isDragging:
    #         self.isDragging = True
    #         self.updateTimer.start(20)

    # def _commitBandUpdate(self):
    #     """Commits the debounced slider values to the ProjectContext."""
    #     r, g, b = self._pendingBandValues
    #     self.proj.updateBand(self.imageIndex, self.bandIndex, r=r, g=g, b=b)
    #     self.isDragging = False

    # def _handleDataChanged(self, index, changeType):
    #     """receives ProjectContext updates. Check if the update pertains to us."""
    #     if index != self.imageIndex:
    #         return
    #     if changeType is not ProjectContext.ChangeType.BAND:
    #         return
    #     r, g, b = self.proj.getImage(self.imageIndex).band[self.bandIndex].toList()
    #     self.sigBandChanged.emit(r, g, b)